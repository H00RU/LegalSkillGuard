# B8 TEST coverage and OpenExempt metrics

Each dataset has 32 source mothers per arm. OpenExempt percentages and mean absolute relative error use only the cases with that official metric available. The parenthetical counts give the number of available scores. The primary score table uses the fixed cohort.

 | Arm | View | Precision (%) | Recall (%) | F1 (%) | MARE | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | Ordinary | EC | 61.07 (32/32) | 38.48 (32/32) | 45.89 (32/32) | Unavailable | 
 | Ordinary | EV | 40.02 (32/32) | 29.34 (32/32) | 31.64 (32/32) | 4.297 (30/32) | 
 | M1 | EC | 61.07 (32/32) | 38.48 (32/32) | 45.89 (32/32) | Unavailable | 
 | M1 | EV | 40.02 (32/32) | 29.34 (32/32) | 31.64 (32/32) | 4.297 (30/32) | 
 | M2 | EC | 61.07 (32/32) | 38.48 (32/32) | 45.89 (32/32) | Unavailable | 
 | M2 | EV | 40.02 (32/32) | 29.34 (32/32) | 31.64 (32/32) | 4.297 (30/32) | 
 | M1 + M2 | EC | 61.07 (32/32) | 38.48 (32/32) | 45.89 (32/32) | Unavailable | 
 | M1 + M2 | EV | 40.02 (32/32) | 29.34 (32/32) | 31.64 (32/32) | 4.297 (30/32) | 
 | PARSE | EC | 62.15 (32/32) | 41.04 (32/32) | 47.53 (32/32) | Unavailable | 
 | PARSE | EV | 38.63 (32/32) | 28.04 (32/32) | 31.05 (32/32) | 2.869 (30/32) | 
 | B0 reference | EC | 60.50 (32/32) | 39.91 (32/32) | 46.18 (32/32) | Unavailable | 
 | B0 reference | EV | 37.17 (32/32) | 24.61 (32/32) | 27.79 (32/32) | 4.879 (29/32) | 

## Official OpenExempt scoring status

 | Arm | View | Source count by status | 
 | --- | ---: | ---: | 
 | Ordinary | EC | scored 32 | 
 | Ordinary | EV | scored 32 | 
 | M1 | EC | scored 32 | 
 | M1 | EV | scored 32 | 
 | M2 | EC | scored 32 | 
 | M2 | EV | scored 32 | 
 | M1 + M2 | EC | scored 32 | 
 | M1 + M2 | EV | scored 32 | 
 | PARSE | EC | scored 32 | 
 | PARSE | EV | scored 32 | 
 | B0 reference | EC | scored 32 | 
 | B0 reference | EV | scored 32 | 

## Native output coverage

 | Arm | Dataset | Handled units | Valid units | Fallback units | Mothers with unhandled units | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | Ordinary | OpenExempt | 64/64 | 64/64 | 0 | 0 | 
 | Ordinary | Diversity | 32/32 | 32/32 | 0 | 0 | 
 | Ordinary | ContractNLI | 544/544 | 544/544 | 0 | 0 | 
 | Ordinary | Airline | 32/32 | 32/32 | 0 | 0 | 
 | Ordinary | MAUD | 96/96 | 96/96 | 0 | 0 | 
 | M1 | OpenExempt | 64/64 | 64/64 | 0 | 0 | 
 | M1 | Diversity | 32/32 | 32/32 | 0 | 0 | 
 | M1 | ContractNLI | 544/544 | 544/544 | 0 | 0 | 
 | M1 | Airline | 32/32 | 32/32 | 0 | 0 | 
 | M1 | MAUD | 96/96 | 96/96 | 0 | 0 | 
 | M2 | OpenExempt | 64/64 | 64/64 | 0 | 0 | 
 | M2 | Diversity | 32/32 | 32/32 | 0 | 0 | 
 | M2 | ContractNLI | 544/544 | 544/544 | 0 | 0 | 
 | M2 | Airline | 32/32 | 32/32 | 0 | 0 | 
 | M2 | MAUD | 96/96 | 96/96 | 0 | 0 | 
 | M1 + M2 | OpenExempt | 64/64 | 64/64 | 0 | 0 | 
 | M1 + M2 | Diversity | 32/32 | 32/32 | 0 | 0 | 
 | M1 + M2 | ContractNLI | 544/544 | 544/544 | 0 | 0 | 
 | M1 + M2 | Airline | 32/32 | 32/32 | 0 | 0 | 
 | M1 + M2 | MAUD | 96/96 | 96/96 | 0 | 0 | 
 | PARSE | OpenExempt | 64/64 | 64/64 | 0 | 0 | 
 | PARSE | Diversity | 32/32 | 32/32 | 0 | 0 | 
 | PARSE | ContractNLI | 510/544 | 510/544 | 0 | 2 | 
 | PARSE | Airline | 32/32 | 32/32 | 0 | 0 | 
 | PARSE | MAUD | 96/96 | 96/96 | 0 | 0 | 
 | B0 reference | OpenExempt | 64/64 | 64/64 | 0 | 0 | 
 | B0 reference | Diversity | 32/32 | 32/32 | 0 | 0 | 
 | B0 reference | ContractNLI | 544/544 | 544/544 | 0 | 0 | 
 | B0 reference | Airline | 32/32 | 32/32 | 0 | 0 | 
 | B0 reference | MAUD | 96/96 | 96/96 | 0 | 0 | 

## Executed routes by source

 | Arm | Dataset | Synthesized interface | Adapted schema | Common program | Compiled fee rules | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | Ordinary | OpenExempt | 0 | 0 | 32 | 0 | 
 | Ordinary | Diversity | 0 | 0 | 32 | 0 | 
 | Ordinary | ContractNLI | 0 | 0 | 32 | 0 | 
 | Ordinary | Airline | 0 | 0 | 26 | 6 | 
 | Ordinary | MAUD | 0 | 0 | 32 | 0 | 
 | M1 | OpenExempt | 0 | 0 | 32 | 0 | 
 | M1 | Diversity | 32 | 0 | 0 | 0 | 
 | M1 | ContractNLI | 0 | 0 | 32 | 0 | 
 | M1 | Airline | 0 | 0 | 26 | 6 | 
 | M1 | MAUD | 0 | 0 | 32 | 0 | 
 | M2 | OpenExempt | 0 | 0 | 32 | 0 | 
 | M2 | Diversity | 0 | 0 | 32 | 0 | 
 | M2 | ContractNLI | 0 | 0 | 32 | 0 | 
 | M2 | Airline | 0 | 0 | 26 | 6 | 
 | M2 | MAUD | 0 | 0 | 32 | 0 | 
 | M1 + M2 | OpenExempt | 0 | 0 | 32 | 0 | 
 | M1 + M2 | Diversity | 32 | 0 | 0 | 0 | 
 | M1 + M2 | ContractNLI | 0 | 0 | 32 | 0 | 
 | M1 + M2 | Airline | 0 | 0 | 26 | 6 | 
 | M1 + M2 | MAUD | 0 | 0 | 32 | 0 | 
 | PARSE | OpenExempt | 0 | 32 | 0 | 0 | 
 | PARSE | Diversity | 0 | 0 | 32 | 0 | 
 | PARSE | ContractNLI | 0 | 32 | 0 | 0 | 
 | PARSE | Airline | 0 | 0 | 26 | 6 | 
 | PARSE | MAUD | 0 | 32 | 0 | 0 | 
 | B0 reference | OpenExempt | 0 | 0 | 32 | 0 | 
 | B0 reference | Diversity | 0 | 0 | 32 | 0 | 
 | B0 reference | ContractNLI | 0 | 0 | 32 | 0 | 
 | B0 reference | Airline | 0 | 0 | 26 | 6 | 
 | B0 reference | MAUD | 0 | 0 | 32 | 0 | 
