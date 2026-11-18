# B8 TEST results

Each arm evaluates 160 fixed source mothers. Scores are percentages. Changes and 95% paired mother bootstrap intervals are in percentage points.

## Native scores

 | Metric | Ordinary | M1 | M2 | M1 + M2 | PARSE | B0 reference | 
 | --- | ---: | ---: | ---: | ---: | ---: | ---: | 
 | OpenExempt EC F1 | 45.89 | 45.89 | 45.89 | 45.89 | 47.53 | 46.18 | 
 | OpenExempt EV F1 | 31.64 | 31.64 | 31.64 | 31.64 | 31.05 | 27.79 | 
 | Diversity accuracy | 78.12 | 81.25 | 78.12 | 81.25 | 78.12 | 78.12 | 
 | Diversity balanced accuracy | 70.83 | 83.33 | 70.83 | 83.33 | 70.83 | 70.83 | 
 | ContractNLI classification accuracy | 55.88 | 55.88 | 55.88 | 55.88 | 52.39 | 50.92 | 
 | ContractNLI evidence F1 | 39.99 | 39.99 | 39.99 | 39.99 | 32.97 | 29.47 | 
 | Airline exact total cost | 18.75 | 18.75 | 18.75 | 18.75 | 18.75 | 18.75 | 
 | MAUD ordinary-course covenant | 90.62 | 90.62 | 90.62 | 90.62 | 90.62 | 93.75 | 
 | MAUD negative-interim covenant | 75.00 | 75.00 | 75.00 | 75.00 | 62.50 | 71.88 | 
 | MAUD knowledge definition | 59.38 | 59.38 | 59.38 | 59.38 | 59.38 | 59.38 | 

## Paired effects

 | Metric | M1 − Ordinary | M2 − Ordinary | M1 + M2 − M2 | M1 + M2 − M1 | M1 + M2 − PARSE | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | OpenExempt EC F1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | -1.65 [-7.48, 4.74] | 
 | OpenExempt EV F1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +0.59 [-4.67, 5.93] | 
 | Diversity accuracy | +3.12 [-18.75, 25.00] | 0.00 [0.00, 0.00] | +3.12 [-18.75, 25.00] | 0.00 [0.00, 0.00] | +3.12 [-18.75, 25.00] | 
 | Diversity balanced accuracy | +12.50 [-5.00, 30.00] | 0.00 [0.00, 0.00] | +12.50 [-5.00, 30.00] | 0.00 [0.00, 0.00] | +12.50 [-5.00, 30.00] | 
 | ContractNLI classification accuracy | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +3.49 [-2.02, 10.11] | 
 | ContractNLI evidence F1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +7.02 [2.43, 11.85] | 
 | Airline exact total cost | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 
 | MAUD ordinary-course covenant | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 
 | MAUD negative-interim covenant | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +12.50 [3.12, 25.00] | 
 | MAUD knowledge definition | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 

## Complete source mothers

OpenExempt counts exact matches on both native views. ContractNLI counts mothers with all classification answers correct and reports evidence F1 in the native scores table.

 | Dataset | Ordinary | M1 | M2 | M1 + M2 | PARSE | B0 reference | 
 | --- | ---: | ---: | ---: | ---: | ---: | ---: | 
 | OpenExempt | 0 | 0 | 0 | 0 | 0 | 0 | 
 | Diversity | 25 | 26 | 25 | 26 | 25 | 25 | 
 | ContractNLI | 0 | 0 | 0 | 0 | 0 | 0 | 
 | Airline | 6 | 6 | 6 | 6 | 6 | 6 | 
 | MAUD | 10 | 10 | 10 | 10 | 9 | 10 | 

## Referenced physical executor usage

 | Arm | Physical calls | Tokens | Executor seconds | 
 | --- | ---: | ---: | ---: | 
 | Ordinary | 192 | 1,122,117 | 1,481.7 | 
 | M1 | 192 | 1,147,945 | 2,057.0 | 
 | M2 | 192 | 1,122,117 | 1,481.7 | 
 | M1 + M2 | 192 | 1,147,945 | 2,057.0 | 
 | PARSE | 192 | 1,125,100 | 1,849.2 | 
 | B0 reference | 192 | 1,087,205 | 1,446.7 | 

The stage added 480 distinct calls, 3,102,630 tokens, and 5,161.9 executor seconds. Shared physical calls can appear in more than one arm row. The local service has no per-request API invoice.
