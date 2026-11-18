# B8 DEV coverage and OpenExempt metrics

Each dataset has 16 source mothers per arm. OpenExempt percentages and mean absolute relative error use only the cases with that official metric available. The parenthetical counts give the number of available scores. The primary score table uses the fixed cohort.

 | Arm | View | Precision (%) | Recall (%) | F1 (%) | MARE | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | Ordinary | EC | 69.53 (16/16) | 41.67 (16/16) | 50.19 (16/16) | Unavailable | 
 | Ordinary | EV | 56.16 (16/16) | 38.19 (16/16) | 44.37 (16/16) | 2.588 (16/16) | 
 | M1 | EC | 69.53 (16/16) | 41.67 (16/16) | 50.19 (16/16) | Unavailable | 
 | M1 | EV | 56.16 (16/16) | 38.19 (16/16) | 44.37 (16/16) | 2.588 (16/16) | 
 | M2 | EC | 69.53 (16/16) | 41.67 (16/16) | 50.19 (16/16) | Unavailable | 
 | M2 | EV | 56.16 (16/16) | 38.19 (16/16) | 44.37 (16/16) | 2.588 (16/16) | 
 | M1 + M2 | EC | 69.53 (16/16) | 41.67 (16/16) | 50.19 (16/16) | Unavailable | 
 | M1 + M2 | EV | 56.16 (16/16) | 38.19 (16/16) | 44.37 (16/16) | 2.588 (16/16) | 
 | PARSE | EC | 68.49 (16/16) | 40.10 (16/16) | 49.50 (16/16) | Unavailable | 
 | PARSE | EV | 56.94 (16/16) | 33.98 (16/16) | 42.08 (16/16) | 0.240 (16/16) | 

## Official OpenExempt scoring status

 | Arm | View | Source count by status | 
 | --- | ---: | ---: | 
 | Ordinary | EC | scored 16 | 
 | Ordinary | EV | scored 16 | 
 | M1 | EC | scored 16 | 
 | M1 | EV | scored 16 | 
 | M2 | EC | scored 16 | 
 | M2 | EV | scored 16 | 
 | M1 + M2 | EC | scored 16 | 
 | M1 + M2 | EV | scored 16 | 
 | PARSE | EC | scored 16 | 
 | PARSE | EV | scored 16 | 

## Native output coverage

 | Arm | Dataset | Handled units | Valid units | Fallback units | Mothers with unhandled units | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | Ordinary | OpenExempt | 32/32 | 32/32 | 0 | 0 | 
 | Ordinary | Diversity | 16/16 | 16/16 | 0 | 0 | 
 | Ordinary | ContractNLI | 272/272 | 272/272 | 0 | 0 | 
 | Ordinary | Airline | 16/16 | 16/16 | 0 | 0 | 
 | Ordinary | MAUD | 48/48 | 48/48 | 0 | 0 | 
 | M1 | OpenExempt | 32/32 | 32/32 | 0 | 0 | 
 | M1 | Diversity | 16/16 | 16/16 | 0 | 0 | 
 | M1 | ContractNLI | 272/272 | 272/272 | 0 | 0 | 
 | M1 | Airline | 16/16 | 16/16 | 0 | 0 | 
 | M1 | MAUD | 48/48 | 48/48 | 0 | 0 | 
 | M2 | OpenExempt | 32/32 | 32/32 | 0 | 0 | 
 | M2 | Diversity | 16/16 | 16/16 | 0 | 0 | 
 | M2 | ContractNLI | 272/272 | 272/272 | 0 | 0 | 
 | M2 | Airline | 16/16 | 16/16 | 0 | 0 | 
 | M2 | MAUD | 48/48 | 48/48 | 0 | 0 | 
 | M1 + M2 | OpenExempt | 32/32 | 32/32 | 0 | 0 | 
 | M1 + M2 | Diversity | 16/16 | 16/16 | 0 | 0 | 
 | M1 + M2 | ContractNLI | 272/272 | 272/272 | 0 | 0 | 
 | M1 + M2 | Airline | 16/16 | 16/16 | 0 | 0 | 
 | M1 + M2 | MAUD | 48/48 | 48/48 | 0 | 0 | 
 | PARSE | OpenExempt | 32/32 | 32/32 | 0 | 0 | 
 | PARSE | Diversity | 16/16 | 16/16 | 0 | 0 | 
 | PARSE | ContractNLI | 272/272 | 272/272 | 0 | 0 | 
 | PARSE | Airline | 16/16 | 16/16 | 0 | 0 | 
 | PARSE | MAUD | 48/48 | 48/48 | 0 | 0 | 

## Executed routes by source

 | Arm | Dataset | Synthesized interface | Adapted schema | Common program | Compiled fee rules | 
 | --- | ---: | ---: | ---: | ---: | ---: | 
 | Ordinary | OpenExempt | 0 | 0 | 16 | 0 | 
 | Ordinary | Diversity | 0 | 0 | 16 | 0 | 
 | Ordinary | ContractNLI | 0 | 0 | 16 | 0 | 
 | Ordinary | Airline | 0 | 0 | 14 | 2 | 
 | Ordinary | MAUD | 0 | 0 | 16 | 0 | 
 | M1 | OpenExempt | 0 | 0 | 16 | 0 | 
 | M1 | Diversity | 16 | 0 | 0 | 0 | 
 | M1 | ContractNLI | 0 | 0 | 16 | 0 | 
 | M1 | Airline | 0 | 0 | 14 | 2 | 
 | M1 | MAUD | 0 | 0 | 16 | 0 | 
 | M2 | OpenExempt | 0 | 0 | 16 | 0 | 
 | M2 | Diversity | 0 | 0 | 16 | 0 | 
 | M2 | ContractNLI | 0 | 0 | 16 | 0 | 
 | M2 | Airline | 0 | 0 | 14 | 2 | 
 | M2 | MAUD | 0 | 0 | 16 | 0 | 
 | M1 + M2 | OpenExempt | 0 | 0 | 16 | 0 | 
 | M1 + M2 | Diversity | 16 | 0 | 0 | 0 | 
 | M1 + M2 | ContractNLI | 0 | 0 | 16 | 0 | 
 | M1 + M2 | Airline | 0 | 0 | 14 | 2 | 
 | M1 + M2 | MAUD | 0 | 0 | 16 | 0 | 
 | PARSE | OpenExempt | 0 | 16 | 0 | 0 | 
 | PARSE | Diversity | 0 | 0 | 16 | 0 | 
 | PARSE | ContractNLI | 0 | 16 | 0 | 0 | 
 | PARSE | Airline | 0 | 0 | 14 | 2 | 
 | PARSE | MAUD | 0 | 16 | 0 | 0 | 
