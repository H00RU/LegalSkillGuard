#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

#include <cuda_runtime.h>

#define CUDA_CHECK(call)                                                        \
    do {                                                                        \
        const cudaError_t error = (call);                                       \
        if (error != cudaSuccess) {                                             \
            std::fprintf(stderr, "%s failed: %s\n", #call,                    \
                         cudaGetErrorString(error));                            \
            return EXIT_FAILURE;                                                \
        }                                                                       \
    } while (0)

__global__ void vector_add(const float* left, const float* right, float* output,
                           int size) {
    const int index = blockIdx.x * blockDim.x + threadIdx.x;
    if (index < size) {
        output[index] = left[index] + right[index];
    }
}

int main() {
    int device_count = 0;
    CUDA_CHECK(cudaGetDeviceCount(&device_count));
    if (device_count < 1) {
        std::fprintf(stderr, "No CUDA device found\n");
        return EXIT_FAILURE;
    }

    cudaDeviceProp properties{};
    CUDA_CHECK(cudaGetDeviceProperties(&properties, 0));

    constexpr int size = 1 << 20;
    constexpr std::size_t bytes = size * sizeof(float);
    std::vector<float> left(size, 1.25F);
    std::vector<float> right(size, 2.75F);
    std::vector<float> output(size, 0.0F);

    float* device_left = nullptr;
    float* device_right = nullptr;
    float* device_output = nullptr;
    CUDA_CHECK(cudaMalloc(&device_left, bytes));
    CUDA_CHECK(cudaMalloc(&device_right, bytes));
    CUDA_CHECK(cudaMalloc(&device_output, bytes));
    CUDA_CHECK(cudaMemcpy(device_left, left.data(), bytes, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(device_right, right.data(), bytes, cudaMemcpyHostToDevice));

    constexpr int threads = 256;
    const int blocks = (size + threads - 1) / threads;
    vector_add<<<blocks, threads>>>(device_left, device_right, device_output, size);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(output.data(), device_output, bytes, cudaMemcpyDeviceToHost));

    CUDA_CHECK(cudaFree(device_left));
    CUDA_CHECK(cudaFree(device_right));
    CUDA_CHECK(cudaFree(device_output));

    for (const float value : output) {
        if (std::fabs(value - 4.0F) > 1e-6F) {
            std::fprintf(stderr, "CUDA result verification failed\n");
            return EXIT_FAILURE;
        }
    }

    int runtime_version = 0;
    int driver_version = 0;
    CUDA_CHECK(cudaRuntimeGetVersion(&runtime_version));
    CUDA_CHECK(cudaDriverGetVersion(&driver_version));
    std::printf(
        "{\"passed\":true,\"device\":\"%s\",\"elements\":%d,"
        "\"runtime_version\":%d,\"driver_api_version\":%d}\n",
        properties.name, size, runtime_version, driver_version);
    return EXIT_SUCCESS;
}
