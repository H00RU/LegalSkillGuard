"""Restore this project's original 8B service; no experiment or teacher calls."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

PROJECT = Path('/media/sangfor/vdb/legal-skill-evolve')
RUNTIME = Path('/media/sangfor/vdb/legal-skill-runtime')
PYTHON = RUNTIME / 'python/cpython-3.11.15-linux-x86_64-gnu/bin/python3.11'
UV = RUNTIME / 'cpu-evidence-ranker-20261015.EB94FZ/bin/uv'
ENV = RUNTIME / 'inference-qwen3-8b-vllm0102'
REVISION = 'b968826d9c46dd6066d109eabc6255188de91218'
MIRROR_REVISION = '7c9709d23bd2136dac1d6ea1fe30f4107d681cd6'
MODEL = RUNTIME / 'models/Qwen3-8B' / REVISION
RECORD = RUNTIME / 'qwen3-8b-restoration-20261018'
FILES = {
    'LICENSE', 'config.json', 'generation_config.json', 'merges.txt',
    'vocab.json', 'tokenizer.json', 'tokenizer_config.json',
    'model.safetensors.index.json',
    *(f'model-{i:05d}-of-00005.safetensors' for i in range(1, 6)),
}


def log(message):
    print(datetime.now(UTC).isoformat(), message, flush=True)


def save(name, data):
    target = RECORD / name
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(target)


def install_environment():
    log('Preparing independent pinned vLLM environment')
    environment = os.environ.copy()
    environment.update(UV_CACHE_DIR=str(RUNTIME / 'uv-inference-cache'),
                       UV_NATIVE_TLS='true', UV_HTTP_TIMEOUT='300')
    environment['NO_PROXY'] = ','.join([environment.get('NO_PROXY', ''),
                                        '.aliyun.com', '.aliyuncs.com'])
    if not (ENV / 'pyvenv.cfg').exists():
        subprocess.run([str(UV), 'venv', '--python', str(PYTHON), str(ENV)],
                       check=True, env=environment)
    subprocess.run([str(UV), 'pip', 'install', '--python', str(ENV / 'bin/python'),
                    '--index-url', 'https://mirrors.aliyun.com/pypi/simple',
                    '--only-binary', ':all:',
                    '-r', str(PROJECT / 'ops/inference-requirements.txt')],
                   check=True, env=environment)
    result = subprocess.run([str(UV), 'pip', 'freeze', '--python', str(ENV / 'bin/python')],
                            check=True, capture_output=True, text=True, env=environment)
    (RECORD / 'installed-packages.txt').write_text(result.stdout)
    subprocess.run([str(UV), 'pip', 'check', '--python', str(ENV / 'bin/python')],
                   check=True, env=environment)
    log('Pinned environment installed and dependency check passed')


def download_file(entry):
    name = entry['rfilename']
    target = MODEL / name
    temporary = MODEL / (name + '.part')
    if not target.exists():
        log(f'Downloading {name} ({entry["size"]} bytes)')
        if name.endswith('.safetensors'):
            # Official Qwen mirror, byte-identical to the pinned HF LFS hashes.
            url = ('https://modelscope.cn/api/v1/models/Qwen/Qwen3-8B/repo'
                   f'?Revision={MIRROR_REVISION}&FilePath={name}')
            transport = ['--noproxy', '*']
        else:
            url = f'https://huggingface.co/Qwen/Qwen3-8B/resolve/{REVISION}/{name}?download=true'
            transport = []
        subprocess.run(['curl', '--disable', '--fail', '--location', '--silent',
                        '--show-error', '--connect-timeout', '20', '--retry', '5',
                        '--retry-delay', '3', '--retry-max-time', '1800',
                        '--speed-limit', '1024', '--speed-time', '120',
                        '--continue-at', '-', '--output', str(temporary),
                        *transport, url], check=True)
        candidate = temporary
    else:
        candidate = target
    if candidate.stat().st_size != entry['size']:
        raise RuntimeError(f'Wrong file size: {name}; retained for diagnosis')
    sha256 = hashlib.sha256()
    git_blob = hashlib.sha1(f'blob {entry["size"]}\0'.encode())
    with candidate.open('rb') as stream:
        while block := stream.read(8 * 1024 * 1024):
            sha256.update(block)
            git_blob.update(block)
    digest = sha256.hexdigest()
    if 'lfs' in entry:
        valid = digest == entry['lfs']['sha256']
    else:
        valid = git_blob.hexdigest() == entry['blobId']
    if not valid:
        raise RuntimeError(f'Official content hash mismatch: {name}; retained for diagnosis')
    if candidate == temporary:
        temporary.replace(target)
    log(f'Verified {name}: {digest}')
    return {'name': name, 'bytes': entry['size'], 'sha256': digest,
            'official_lfs_sha256_or_git_blob_verified': True}


def restore_weights():
    url = f'https://huggingface.co/api/models/Qwen/Qwen3-8B/revision/{REVISION}?blobs=true'
    with urllib.request.urlopen(url, timeout=45) as response:
        metadata = json.load(response)
    if metadata['sha'] != REVISION or metadata['id'] != 'Qwen/Qwen3-8B':
        raise RuntimeError('Official model identity/revision mismatch')
    entries = [entry for entry in metadata['siblings'] if entry['rfilename'] in FILES]
    if {entry['rfilename'] for entry in entries} != FILES:
        raise RuntimeError('Official model file list is incomplete')
    save('official-model-metadata.json', metadata)
    mirror_url = ('https://modelscope.cn/api/v1/models/Qwen/Qwen3-8B/repo/files'
                  f'?Revision={MIRROR_REVISION}&Recursive=true')
    with urllib.request.urlopen(mirror_url, timeout=45) as response:
        mirror = json.load(response)
    mirror_files = {item['Name']: item for item in mirror['Data']['Files']}
    for entry in entries:
        if entry['rfilename'].endswith('.safetensors'):
            same = mirror_files[entry['rfilename']]
            if same['Sha256'] != entry['lfs']['sha256'] or same['Size'] != entry['size']:
                raise RuntimeError('Official mirror does not match pinned HF weight content')
    save('official-mirror-matching-metadata.json', mirror)
    # Small metadata first, then up to three resumable shard transfers.
    entries.sort(key=lambda item: item['size'])
    with ThreadPoolExecutor(max_workers=3) as pool:
        manifest = list(pool.map(download_file, entries))
    index = json.loads((MODEL / 'model.safetensors.index.json').read_text())
    if set(index['weight_map'].values()) != {name for name in FILES if name.endswith('.safetensors')}:
        raise RuntimeError('Weight index does not match verified shards')
    save('verified-model-manifest.json', {'repository': 'Qwen/Qwen3-8B',
         'revision': REVISION, 'weight_transport': 'official Qwen ModelScope direct',
         'weight_transport_revision': MIRROR_REVISION, 'files': manifest,
         'old_original_weight_hash_unrecovered_not_bitwise_identity_claim': True})
    log('All model files verified against the pinned official revision')


def main():
    MODEL.mkdir(parents=True, exist_ok=True)
    RECORD.mkdir(parents=True, exist_ok=True)
    save('restore-state.json', {'state': 'restoring', 'started_at': datetime.now(UTC).isoformat(),
         'user_authorized_same_model_restoration': True, 'no_training_or_teacher_calls': True})
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            weights = pool.submit(restore_weights)
            environment = pool.submit(install_environment)
            weights.result()
            environment.result()
        subprocess.run(['systemctl', '--user', 'start', 'legal-qwen3-8b.service'], check=True)
        save('restore-state.json', {'state': 'verified_files_and_environment_service_start_requested',
             'at': datetime.now(UTC).isoformat(), 'service_health_and_inference_still_require_check': True})
        log('Requested background service start; readiness is not yet claimed')
    except BaseException as error:
        save('restore-state.json', {'state': 'failed', 'at': datetime.now(UTC).isoformat(),
                                  'error': f'{type(error).__name__}: {error}'})
        raise


if __name__ == '__main__':
    main()
