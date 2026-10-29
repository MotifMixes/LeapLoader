/* Leapster instruments: the program numbers the BIOS synth plays (LeapLoader SDK, zlib licence).
   In a LeapFrog music sequence the command `89 p` picks instrument p for that track
   (format: docs/HANDOFF.md "Music"; research/seqgen.py writes it). Names: the
   community "LeapFrog Leap-Font" soundfont (bank 0), mostly LeapFrog's own hINSTR_ names.
   Numbers that are missing have no instrument. The SDK has no music call yet. */
#ifndef LL_INSTRUMENTS_H
#define LL_INSTRUMENTS_H

#define LL_INSTR_LONGPIANO            0
#define LL_INSTR_PIANO                1
#define LL_INSTR_BASSDRUM             2 /* in no game music (83 titles) */
#define LL_INSTR_2ND_GRADE_INSTRUMENT 3 /* in no game music (83 titles) */
#define LL_INSTR_RHODESPIANO          4
#define LL_INSTR_WURLPIANO            5
#define LL_INSTR_CLAVINET             7
#define LL_INSTR_GLOCKSMALL           9
#define LL_INSTR_VIBELONG            11
#define LL_INSTR_MARIMBA             12
#define LL_INSTR_HAMDULCIMER         15
#define LL_INSTR_ORGAN               17
#define LL_INSTR_B3ORGAN             18
#define LL_INSTR_LEAPSTERORGAN       19
#define LL_INSTR_HARMONIUM           20
#define LL_INSTR_LPTRACCORDION       21
#define LL_INSTR_NYLONSTRINGGT       24
#define LL_INSTR_MELECTGUITAR        26 /* in no game music (83 titles) */
#define LL_INSTR_LEAPSTER27          27
#define LL_INSTR_MUTEDELECTGT        28
#define LL_INSTR_ELECTGUIT           29 /* in no game music (83 titles) */
#define LL_INSTR_ROCKGUITAR          30
#define LL_INSTR_CLEANELECGUIT       31
#define LL_INSTR_ACOUSTICBASS        32
#define LL_INSTR_ELECTRICBASS        33
#define LL_INSTR_MACOUSTICBASS       35
#define LL_INSTR_MELECTBASS          37
#define LL_INSTR_SYNTHBASS           38
#define LL_INSTR_SOLOVIOLIN          40 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRVIOLIN         41
#define LL_INSTR_PRESET43            43
#define LL_INSTR_INSTRUMENT_44       44
#define LL_INSTR_SYNTHSTRINGS        48
#define LL_INSTR_LEAPSTER_SQ         50
#define LL_INSTR_LEAPSTER_SAW        51
#define LL_INSTR_LPSTR_SAWBASS       52
#define LL_INSTR_LEAPSTER_SINE       53
#define LL_INSTR_LPS_NEEDSNAME       54
#define LL_INSTR_LPSTR_DSBAS         55
#define LL_INSTR_TRUMPETB            56
#define LL_INSTR_TROMBONE            57
#define LL_INSTR_TUBA                58
#define LL_INSTR_LPSTRARCADE1        59 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE2        60 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE3        61 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE4        62 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE5        63 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE6        64 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE7        65 /* in no game music (83 titles) */
#define LL_INSTR_TENORSAX            66
#define LL_INSTR_OBOE                68
#define LL_INSTR_BASSOON             70
#define LL_INSTR_CLARINET            71
#define LL_INSTR_FLUTE               73
#define LL_INSTR_LPSTRARCADE8        74 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE9        75 /* in no game music (83 titles) */
#define LL_INSTR_LEAPSTERTHING       76 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE10       77 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRTHING2         79
#define LL_INSTR_SYNTHWAVES          80 /* in no game music (83 titles) */
#define LL_INSTR_LPSRARCADECAT       81 /* in no game music (83 titles) */
#define LL_INSTR_CALLIOPE            82
#define LL_INSTR_SYNBLIPS            83
#define LL_INSTR_SQBLIPS             84
#define LL_INSTR_FIFTHSRCKGTR        86
#define LL_INSTR_SYNTHMINIMOOG       87
#define LL_INSTR_GAMLAN              89 /* in no game music (83 titles) */
#define LL_INSTR_JEWSHARP            90
#define LL_INSTR_WACKYSTUFF          94
#define LL_INSTR_SYNTHREZZSW         95 /* in no game music (83 titles) */
#define LL_INSTR_SNYLONSGUIT         97
#define LL_INSTR_NSGM50C             98 /* in no game music (83 titles) */
#define LL_INSTR_MPIANO              99
#define LL_INSTR_LEAPSTERBROMSFX    100
#define LL_INSTR_ODYSSEYOEPERC      103 /* in no game music (83 titles) */
#define LL_INSTR_SITAR              104
#define LL_INSTR_LEAPSTERBANJO      105
#define LL_INSTR_KALIMBA            108
#define LL_INSTR_LPSTRARCADE11      109 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE12      110 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE13      111 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE14      112 /* in no game music (83 titles) */
#define LL_INSTR_LPSTRARCADE15      113 /* in no game music (83 titles) */
#define LL_INSTR_STEELDRUM          114
#define LL_INSTR_WOODBLK_CLAVE      115
#define LL_INSTR_PERCA_STNDRD       119 /* in no game music (83 titles) */
#define LL_INSTR_PERCB_ETHNIC       120
#define LL_INSTR_PERCC_METAL        121
#define LL_INSTR_PERCE_MISC         123
#define LL_INSTR_PERCF_SUPRKIT      124
#define LL_INSTR_PERCG_ALTELEC      125
#define LL_INSTR_PERCGENMIDI        126
#define LL_INSTR_NULL               127 /* "Null"; the most common program change in game music */

#endif
