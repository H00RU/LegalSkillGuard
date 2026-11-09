"""Reproduce the fixed TRAIN7 arithmetic audit; not a model or oracle solver."""
from itertools import combinations
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[2]
def main():
 proof=json.loads((Path(__file__).with_name('TRAIN7_native_and_order_contract_audit.json')).read_text())
 source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==proof['source'])
 bags=[(int(i),sum(map(int,(a,b,c))),int(w)) for i,a,b,c,w in re.findall(r'(\d+)\. A [^:]+: (\d+) x (\d+) x (\d+) inches, (\d+) lbs',source['public']['prompt'])]
 assert len(bags)==11 and bags[0][0]==1
 rules=source['public']['rules']
 assert all(s in rules for s in ('Weight: 70 lbs / 32kgs for complimentary bags and 50 lbs / 23 kgs for excess charged bags','The higher fee between oversize and overweight applies','1st and 2nd checked bags are complimentary'))
 def fee(size,weight,free):
  oversize=0 if size<=62 else 30 if size<=65 else 200
  overweight=0 if weight<=(70 if free else 50) else 30 if weight<=53 else 100 if weight<=70 else None
  assert overweight is not None
  return (0 if free else 200)+max(oversize,overweight)
 base=int(re.search(r'flight ticket is \$(\d+)',source['public']['prompt'])[1])
 totals={free:base+sum(fee(s,w,i in free) for i,s,w in bags[1:]) for free in combinations([i for i,_,_ in bags[1:]],2)}
 assert totals[(2,3)]==proof['listed_order_total']==3835
 assert min(totals.values())==proof['minimum_assignment_total']==3695
 print(json.dumps({'listed':totals[(2,3)],'minimum':min(totals.values()),'interpretations':len(totals),'model_or_oracle_calls':0}))
if __name__=='__main__':main()
