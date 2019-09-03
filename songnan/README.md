# Lexer for the Semparser

## files and documents
	1. squan@clc-alpage-1.linguist.univ-paris-diderot.fr:/home/squan/files
	   a) wikidata-20180101-all.json.bz2   - dump Wikidata
	   b) graph-0430.txt                   - graph generated from the dump wikidata for relevant items 
	                                         (29,457,285 out of 78,906,205), represented by Wikidata IDs
	   c) file2pr_v1.txt, file2pr_v2.txt   - 2 versions of graph represented by integers 
	                                         (not by Wikidata IDs)
	   d) dico_e2c_c2e.txt                 - correspondance of Wikidata IDs and integers
	   e) pagerank_v1.txt, pagerank_v1.txt - 2 versions of PageRank score calculated for 29,973,127 items,
                                             for both entities and relations
	
	2. squan@clc-alpage-1.linguist.univ-paris-diderot.fr:/data/squan/
	   a) files
          1) extract_human.py 
             human_dico.json               - extract and store all human names in Wikidata (3,406,079)
          2) dico_entities_1/2.json        - all relevant items extracted from Wikidata (29,457,285)
          3) pagerank_v1/2.txt             - 2 versions of PageRank score calculated for 29,973,127 items,
                                             for both entities and relations

	   b) makedico                         - file where we can generate the dictionnary 
	   									     possible to choose the size of the dictionnary
	   	  1) dico_entities_1/2.json        - all relevant items extracted from Wikidata (29,457,285)
	   	  2) littledico1/2.json            - internal files for the dictionnary extraction
	   	  3) dico_quan1/2.json             - dictionnary to be used for the lexer and semparser

	   c) test                             - test the lexer and semparser
	      1) dico_quan1/2.json             - dictionnary used for lexer
	      2) lexer_quan.py
	         lexerpytrie_quan.py
	         lexerdatrie_quan.py           - 3 versions of lexer
	      3) my.trie                       - trie pre-stored for datrie
	      4) get_characters.py             - gathers all possible characters in the corpora
	      5) chs.json                      - all possible characters in the corpora
	      6) simple.json, simple.out
	         bridging.json, bridging.out
	         introuvable.json
	         introuvable.out               - question tests and output

## calculation of Pagerank (already prepared)
	uses the code in https://github.com/louridas/pagerank

	Already calculated, results in pagerank_v1/2.txt
	(in squan@clc-alpage-1.linguist.univ-paris-diderot.fr:/home/squan/files and squan@clc-alpage-1.linguist.univ-paris-diderot.fr:/data/squan/files).

## extract entities (already prepared)
	Already executed, results in dico_entities_1/2.json
	(in squan@clc-alpage-1.linguist.univ-paris-diderot.fr:/data/squan/makedico and squan@clc-alpage-1.linguist.univ-paris-diderot.fr:/data/squan/files)

## generate the dictionnary
	extract.py, dico_entities_1.json, dico_entities_2.json 
	(in squan@clc-alpage-1.linguist.univ-paris-diderot.fr:/data/squan/makedico)
	modify line 232 and 237 for the value of "max_size"
	output : 2 dictionnaires -> dico_quan1.json and dico_quan2.json.

	how to use: "python3 extract.py" in the terminal, can modify line 232 and 237 for "max_size"

## load the lexer
	3 versions, using RegEx (lexer_quan.py), pytrie (lexerpytrie_quan.py) or datrie (lexerdatrie_quan.py)
	in squan@clc-alpage-1.linguist.univ-paris-diderot.fr:/data/squan/test
	the value for variable "max_vocab_size" can be changed (line 294)

	how to use: "python3 lexerdatrie_quan.py" in the terminal

## use the semparser
	to execute in squan@clc-alpage-1.linguist.univ-paris-diderot.fr:/data/squan/test
	how to use: "python3 semparser", can change the name of file to test in line 745
	(p.eval_songnan('xxx.json',beam_size=500,lr=1.0,epochs=5), xxx can be: simple/bridging/introuvable/total.json)





