# B4 DEV results

Each arm evaluates 80 fixed source mothers. Scores are percentages. Changes and 95% paired mother bootstrap intervals are in percentage points.

## Native scores

 | Metric | Ordinary | M1 | M2 | M1 + M2 | PARSE | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | OpenExempt EC F1 | 17.09 | 17.09 | 25.08 | 25.08 | 24.59 | 
 | OpenExempt EV F1 | 15.49 | 15.49 | 16.12 | 16.12 | 16.44 | 
 | Diversity accuracy | 56.25 | 87.50 | 56.25 | 87.50 | 56.25 | 
 | Diversity balanced accuracy | 56.25 | 87.50 | 56.25 | 87.50 | 56.25 | 
 | ContractNLI classification accuracy | 57.35 | 57.35 | 57.35 | 57.35 | 54.78 | 
 | ContractNLI evidence F1 | 36.37 | 36.37 | 36.37 | 36.37 | 25.57 | 
 | Airline exact total cost | 12.50 | 12.50 | 12.50 | 12.50 | 12.50 | 
 | MAUD ordinary-course covenant | 87.50 | 87.50 | 87.50 | 87.50 | 81.25 | 
 | MAUD negative-interim covenant | 68.75 | 68.75 | 68.75 | 68.75 | 62.50 | 
 | MAUD knowledge definition | 50.00 | 50.00 | 50.00 | 50.00 | 50.00 | 

## Paired effects

 | Metric | M1 − Ordinary | M2 − Ordinary | M1 + M2 − M2 | M1 + M2 − M1 | M1 + M2 − PARSE | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | OpenExempt EC F1 | 0.00 [0.00, 0.00] | +8.00 [0.54, 16.04] | 0.00 [0.00, 0.00] | +8.00 [0.54, 16.04] | +0.49 [-3.93, 5.32] | 
 | OpenExempt EV F1 | 0.00 [0.00, 0.00] | +0.63 [-2.95, 4.00] | 0.00 [0.00, 0.00] | +0.63 [-2.95, 4.00] | -0.32 [-4.06, 3.40] | 
 | Diversity accuracy | +31.25 [0.00, 56.25] | 0.00 [0.00, 0.00] | +31.25 [0.00, 56.25] | 0.00 [0.00, 0.00] | +31.25 [0.00, 56.25] | 
 | Diversity balanced accuracy | +31.25 [6.25, 56.25] | 0.00 [0.00, 0.00] | +31.25 [6.25, 56.25] | 0.00 [0.00, 0.00] | +31.25 [6.25, 56.25] | 
 | ContractNLI classification accuracy | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +2.57 [-2.21, 7.35] | 
 | ContractNLI evidence F1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +10.80 [5.87, 16.07] | 
 | Airline exact total cost | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 
 | MAUD ordinary-course covenant | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +6.25 [0.00, 18.75] | 
 | MAUD negative-interim covenant | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | +6.25 [-18.75, 31.25] | 
 | MAUD knowledge definition | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 

## Complete source mothers

OpenExempt counts exact matches on both native views. ContractNLI counts mothers with all classification answers correct and reports evidence F1 in the native scores table.

 | Dataset | Ordinary | M1 | M2 | M1 + M2 | PARSE | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | OpenExempt | 0 | 0 | 0 | 0 | 0 | 
 | Diversity | 9 | 14 | 9 | 14 | 9 | 
 | ContractNLI | 0 | 0 | 0 | 0 | 0 | 
 | Airline | 2 | 2 | 2 | 2 | 2 | 
 | MAUD | 6 | 6 | 6 | 6 | 4 | 

## Referenced physical executor usage

 | Arm | Physical calls | Tokens | Executor seconds | 
 | --- | ---: | ---: | ---: | 
 | Ordinary | 96 | 652,868 | 2,486.1 | 
 | M1 | 96 | 665,892 | 2,779.8 | 
 | M2 | 96 | 603,045 | 1,217.6 | 
 | M1 + M2 | 96 | 616,069 | 1,511.2 | 
 | PARSE | 96 | 603,974 | 1,304.6 | 

The stage added 121 distinct calls, 935,794 tokens, and 3,547.9 executor seconds. Shared physical calls can appear in more than one arm row. The local service has no per-request API invoice.
