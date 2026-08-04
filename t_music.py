[33mcommit 3671b45b1235f8babcd57493d0f694385cd750ef[m[33m ([m[1;36mHEAD[m[33m -> [m[1;32mredesign[m[33m, [m[1;31morigin/redesign[m[33m)[m
Author: superficiallylucid <superficiallylucid@gmail.com>
Date:   Tue Aug 4 14:01:34 2026 -0400

    Add initial chord library support

 CHANGELOG.md                                       |  65 [32m+++++[m
 banjo_chord_library.csv                            |   4 [32m+[m
 banjo_chord_library.gsheet                         |   1 [32m+[m
 build/BanjoOptimizer/Analysis-00.toc               | 124 [32m++++[m[31m-----[m
 build/BanjoOptimizer/BanjoOptimizer.pkg            | Bin [31m8815115[m -> [32m8814588[m bytes
 build/BanjoOptimizer/EXE-00.toc                    |   2 [32m+[m[31m-[m
 build/BanjoOptimizer/PYZ-00.pyz                    | Bin [31m1796735[m -> [32m1796914[m bytes
 build/BanjoOptimizer/base_library.zip              | Bin [31m1394480[m -> [32m1394480[m bytes
 .../banjo_chord_library - gDGBD Chord Shapes.csv   | 166 [32m++++++++++++[m
 dist/BanjoOptimizer.exe                            | Bin [31m9162763[m -> [32m9162236[m bytes
 dist/scores/Moon River (G).mscz                    | Bin [31m53964[m -> [32m0[m bytes
 dist/scores/Moonglow (gCGBbD).mscz                 | Bin [31m0[m -> [32m127942[m bytes
 files.zip                                          | Bin [31m0[m -> [32m8222[m bytes
 main.py                                            |  47 [32m++[m[31m--[m
 models.py                                          |  58 [32m++++[m[31m-[m
 music.py                                           | 201 [32m+++++++++++++[m[31m-[m
 optimizer.py                                       |  88 [32m++++++[m[31m-[m
 parser.py                                          | 173 [32m+++++++++++[m[31m-[m
 recommendations.py                                 |  64 [32m+++++[m
 scores/Moonglow (gCGBbD).mscz                      | Bin [31m0[m -> [32m127942[m bytes
 scores/White Christmas (G (gCGBD)).mscz            | Bin [31m93081[m -> [32m0[m bytes
 test_music.py                                      | 289 [32m+++++++++++++++++++++[m
 22 files changed, 1186 insertions(+), 96 deletions(-)
