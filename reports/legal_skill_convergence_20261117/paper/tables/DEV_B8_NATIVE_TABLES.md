# B8 DEV results

Each arm evaluates 80 fixed source mothers. Scores are percentages. Changes and 95% paired mother bootstrap intervals are in percentage points.

## Native scores

 | Metric | Ordinary | M1 | M2 | M1 + M2 | PARSE | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | OpenExempt EC F1 | 50.19 | 50.19 | 50.19 | 50.19 | 49.50 | 
 | OpenExempt EV F1 | 44.37 | 44.37 | 44.37 | 44.37 | 42.08 | 
 | Diversity accuracy | 56.25 | 87.50 | 56.25 | 87.50 | 56.25 | 
 | Diversity balanced accuracy | 56.25 | 87.50 | 56.25 | 87.50 | 56.25 | 
 | ContractNLI classification accuracy | 57.35 | 57.35 | 57.35 | 57.35 | 54.41 | 
 | ContractNLI evidence F1 | 36.37 | 36.37 | 36.37 | 36.37 | 26.46 | 
 | Airline exact total cost | 12.50 | 12.50 | 12.50 | 12.50 | 12.50 | 
 | MAUD ordinary-course covenant | 87.50 | 87.50 | 87.50 | 87.50 | 87.50 | 
 | MAUD negative-interim covenant | 56.25 | 56.25 | 56.25 | 56.25 | 56.25 | 
 | MAUD knowledge definition | 50.00 | 50.00 | 50.00 | 50.00 | 62.50 | 

## Paired effects

 | Metric | M1 − Ordinary | M2 − Ordinary | M1 + M2 − M2 | M1 + M2 − M1 | M1 + M2 − PARSE | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | OpenExempt EC F1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +0.69 [-1.39, 3.82] | 
 | OpenExempt EV F1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +2.28 [-0.67, 7.19] | 
 | Diversity accuracy | +31.25 [0.00, 56.25] | 0.00 [0.00, 0.00] | +31.25 [0.00, 56.25] | 0.00 [0.00, 0.00] | +31.25 [0.00, 56.25] | 
 | Diversity balanced accuracy | +31.25 [6.25, 56.25] | 0.00 [0.00, 0.00] | +31.25 [6.25, 56.25] | 0.00 [0.00, 0.00] | +31.25 [6.25, 56.25] | 
 | ContractNLI classification accuracy | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +2.94 [-2.21, 8.46] | 
 | ContractNLI evidence F1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +9.91 [4.38, 15.42] | 
 | Airline exact total cost | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 
 | MAUD ordinary-course covenant | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 
 | MAUD negative-interim covenant | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 
 | MAUD knowledge definition | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | -12.50 [-31.25, 0.00] | 

## Complete source mothers

OpenExempt counts exact matches on both native views. ContractNLI counts mothers with all classification answers correct and reports evidence F1 in the native scores table.

 | Dataset | Ordinary | M1 | M2 | M1 + M2 | PARSE | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | OpenExempt | 0 | 0 | 0 | 0 | 0 | 
 | Diversity | 9 | 14 | 9 | 14 | 9 | 
 | ContractNLI | 0 | 0 | 0 | 0 | 0 | 
 | Airline | 2 | 2 | 2 | 2 | 2 | 
 | MAUD | 4 | 4 | 4 | 4 | 5 | 

## Referenced physical executor usage

 | Arm | Physical calls | Tokens | Executor seconds | 
 | --- | ---: | ---: | ---: | 
 | Ordinary | 96 | 592,335 | 709.1 | 
 | M1 | 96 | 605,359 | 1,002.8 | 
 | M2 | 96 | 592,335 | 709.1 | 
 | M1 + M2 | 96 | 605,359 | 1,002.8 | 
 | PARSE | 96 | 589,451 | 758.6 | 

The stage added 112 distinct calls, 846,531 tokens, and 1,083.1 executor seconds. Shared physical calls can appear in more than one arm row. The local service has no per-request API invoice.
