#! /usr/bin/env python

"""
Dummy lexer, this is basically a translation with slight variations of the C++ version used in nlp-toolbox
"""
import re
import json

from lambda_parser import FuncParser
from functional_core import TypeSystem
from wikidata_model import WikidataModelInterface,NamingContextWikidata
import pytrie
from pytrie import SortedStringTrie as Trie
import datetime

class Token:
	
	def __init__(self,wform,ptag,logmacro,logform):
		"""
		Args:
			wform              (string) : the raw string
			ptag               (string) : the pos tag of the token
			logmacro           (string) : a wikidata Qxxx or Pxxx identifier
			logical_macro (LambdaTerm) : a lambda term for the macro
		"""
		self.form          = wform
		self.postag        = ptag
		self.logical_macro = logmacro
		self.logical_form  = logform
		self.logical_type  = TypeSystem.typecheck(logform)  if logform else None

	def is_predicate(self):
		return not self.logical_macro is None and self.logical_macro[0] == 'P'
	
	def is_entity(self):
		return  not self.logical_macro is None and self.logical_macro[0] == 'Q'
		
	def __str__(self):
		return "%s/%s"%(self.form,self.logical_macro)

	
class Tokenizer:
	"""
	CONLL-U tokenizer
	@see examples.conllu
	"""
	def __init__(self,filename,LFdictionary):
		"""
		@param filename: the name of a conllu file to parse
		@param LFdictionary: a dictionary mapping macro names to
		lambda terms
		"""
		self.istream = open(filename)
		self.LFdict = LFdictionary
			
	def read_conllu_input(self,ref_answer=False):
		"""
		This reads in the next sentence in a conllu file
		@param istream: the input stream to the file
		@param ref_answer : returns additionnaly the ref answer list 
		@return a list of Tokens, and optionally the reference answer list
		"""
		line        = self.istream.readline()
		toklist     = [ ]
		skip_idxes  = set([ ])
		ref_answers = [ ]
		while not line.isspace() and line != '':
			if line[0] == '0':
				ref_answers = line.split()
				ref_answers.pop(0)
			else:
				idxrange,surf_string,postag,logical_macro = line.split()
				if '-' in idxrange:
					startidx,endidx = idxrange.split('-')
					startidx,endidx = int(startidx),int(endidx)
					skip_idxes.update(list(range(startidx,endidx+1)))
					toklist.append(Token(surf_string,postag,logical_macro,self.LFdict.get(logical_macro,None)) ) 
				else:
					idx = int(idxrange)
					if idx not in skip_idxes:
						toklist.append( Token(surf_string,postag,logical_macro,self.LFdict.get(logical_macro,None)) )
			line = self.istream.readline()
		if not toklist:
			self.istream.close()
		if ref_answer:
			return (toklist,ref_answers)
		return toklist

class DefaultLexer:
	
	def __init__(self,cpd_file,entity_file=None):
		self.compile_regexes()
		self.compile_cpd(cpd_file)
		self.mwe_regex = None
		self.compile_mwe(entity_file)

		#Lambda parser for building lexical terms from wikidata IDs
		wikidata_model     = WikidataModelInterface()
		wikidata_names     = NamingContextWikidata.make_wikidata_builtins_context(debug=True)
		self.lambda_parser = FuncParser(wikidata_names,wikidata_model)

		#should externalize this
		self.wh_words = set(['Qui','Que','Quel','Quelle','Quels','Quelles','Où','qui','quel','quelle','quels','quelles','où'])
		self.wh_term = self.lambda_parser.parse_code('(lambda (P:e=>t) (@exists(x:e) (P x)))')

		self.and_words = set(['et'])
		self.or_words  = set(['ou'])

	def tokenize_json(self,line,ref_answer=False): 
		"""
		Tokenizes a json utterance. The json is expected to be
		structured using WebQuestions schema.

		Wraps the lexer internals into a Token list.

		TODO : integrate a POS Tagger in the lexer

		Args: 
		   line     (string): a json line from webquestions style data set
		KwArgs:
		   ref_answer (bool): returns the reference answer too
		Returns: 
		   A list of Token objects or a couple (list of Token, list of ref answers)
		"""
		jline   = json.loads(line)     
		query   = jline['utterance_fr']  

		#Segmentation 
		toklist = self.tokenize_line(query)

		#Linking & POS tagging (pos not done)
		def link_entity(ent_list): 
			"""
			Selects brutally an entity among the entity candidates for this token
			"""
			if ent_list:
				for e in ent_list:
					if e[0] == 'P': #hack for properties (with null page-rank)
						return e
				return ent_list[0]
			return None
		 
		tokens = [ ]
		for tokform,entity_list in toklist:
			print(tokform,entity_list)
			qmacro   = None
			qlogform = None
			if tokform in self.and_words:
				qmacro = 'AND'
			elif tokform in self.or_words:
				qmacro = 'OR'
			elif entity_list:
				qmacro   = link_entity(entity_list) 
				if qmacro[0] == 'Q':
					qlogform = self.lambda_parser.parse_code('wd:'  + qmacro)
				else:
					qlogform = self.lambda_parser.parse_code('wdt:' + qmacro)
			elif tokform in self.wh_words:
				 qmacro   = 'WHQ'
				 qlogform = self.wh_term.copy()  
			tokens.append( Token(tokform,"NOTAG",qmacro,qlogform)) 
  
		#Reference answers
		if ref_answer:
 			janswer     = jline['targetValue'].strip()
 			answer_list = []
 			for answer in janswer.split(','):
 				 answer_list.append(answer)
			#janswer     = jline['targetValue'].strip()
			#janswer      = janswer[6:-1] #strips outer (list ... )
			#answer_list = []
			#pattern = re.compile(r'\(description ([^\)]+)\)')
			#for answ_match in pattern.finditer(janswer):
			#	answ = answ_match.group(1)
			#	if answ[0] == '"' and answ[-1] == '"':
			#		answ = answ[1:-1]
			#	answer_list.append(answ)

		return (tokens,answer_list)
		 
	def tokenize_line(self,line):
		"""
		Tokenizes a regular line 
		Args:
		   line (string): a string to tokenize
		"""
		try:
			self.set_line(line)
			toklist = [ self.next_token() ]
			while not toklist[-1] is None:
				toklist.append( self.next_token())
			toklist.pop()
			return toklist
		except Exception as e:
			print(e)
	
		return [ ]
 
	def next_token(self,K=5):

		#1. skips any leading wsp
		match = self.wsp_regex.match(self.inner_bfr,pos=self.idx)
		if match:
			self.idx = match.end()

		#2. Attempts to match strong cpd
		match = self.cpd_regex.match(self.inner_bfr,pos=self.idx)
		if match:
			token    = self.inner_bfr[ self.idx:match.end() ]
			self.idx = match.end() 
			return ( token.replace(' ','') , [ ] )
		
		#3. Attempts to match MWE
		if self.mwe_regex:
			match = self.mwe_regex.longest_prefix_value(self.inner_bfr[self.idx:], -1)
			if match != -1:
				match = self.mwe_regex.longest_prefix(self.inner_bfr[self.idx:])
				token       = self.inner_bfr[self.idx:( self.idx+len(match) )]
				self.idx    = ( self.idx+len(match) )
				entity_list = self.entity_dict.get(token, [] )
				return ( token, entity_list ) 
 
		#2 and #3 should be swapped ?
		
		#4. Regular default match
		match = self.full_regex.match(self.inner_bfr,pos=self.idx)
		if match:
			token       = self.inner_bfr[self.idx:match.end()]
			self.idx    = match.end()
			entity_list = self.entity_dict.get(token,[])
			return ( token, entity_list )
		
		return None 

	def lookup_entity(self,wordform):
		
		return self.entity_dic.get(wordform,'NONE')

	def set_line(self,line):
		"""
		The buffer on which the tokenizer operates
		"""
		self.inner_bfr = self.normalize_string(line)
		self.idx       = 0

	#Normalization
	def tr_char(self,c):
		 if  c in '“”»«':
			 return '"'
		 elif c in "‘’":
			 return "'"
		 else: 
			 return c

	def tr_string(self,bfr):
		"""
		Normalizes punct mark
		"""
		return ''.join([self.tr_char(c) for c in bfr])

	def normalize_string(self,bfr):
		if bfr:
			bfr = self.tr_string(bfr)    
			bfr = re.sub(self.norm_ponct_regex,r" \1 ",bfr)  
			bfr = re.sub(self.norm_dots_regex,"...",bfr)    
			bfr = re.sub(self.norm_wsp_regex," ",bfr)       
			bfr = re.sub(self.norm_apos_regex,"'",bfr)      
			bfr = re.sub(self.norm_oe_regex,"oe",bfr)        
			if bfr[0] == ' ':
				bfr = bfr[1:]
			if bfr[-1] == ' ':
				bfr[:-1]
		return bfr

	
	def compile_regexes(self):
		#norm regexes
		self.norm_ponct_regex = re.compile(r"([\?!\{;,\}\.:/=\+\(\)\[\]\"'\-…])")
		self.norm_dots_regex  = re.compile(r"…")
		self.norm_wsp_regex   = re.compile(r"([ \n\s\t])+")
		self.norm_apos_regex  = re.compile(r" '")
		self.norm_oe_regex    = re.compile(r"œ")


		self.wsp_regex = re.compile("([ \n\s\t]+)")
		self.full_regex = re.compile("([^ \n\s\t]+)")

	def compile_mwe(self,filename,max_vocab_size=545913):
		# max_vocab_size=4459136
		self.entity_dict = {}
		if filename:
			istream = open(filename)
			keylist = {}
			idx = 0
			line = istream.readline()
			print(datetime.datetime.now())
			while line:
				line    = json.loads(line)
				key     = line['named_entity']
				vallist = list(line['entity_list'])
				self.entity_dict[key] = vallist
				if ' ' in key:
				   keylist[key] = idx
				idx += 1
				if idx > max_vocab_size:
				   break
				line = istream.readline()
			print(datetime.datetime.now())

			#self.mwe_regex = sorted(keylist,reverse=True,key=lambda x:len(x))
			self.mwe_regex = Trie(keylist)
			print(datetime.datetime.now())
			istream.close() 
		else:
			self.mwe_regex = None
			
	def compile_cpd(self,filename):
		
		istream = open(filename)
		self.cpd_regex  = '('  +  '|'.join([' | '.join(line.split('+')) for line in istream])
		istream.close() 

		self.cpd_regex += r" ([0-9]+( ([/,\.])? ?[0-9]+)+)"         #numbers/dates sub expression 
		self.cpd_regex += r"|([0-9]+( (ème|eme|er|e|è) ))"          # (partially including ordinals)
		self.cpd_regex += r"|( ?\-)+"                               # hyphens
		self.cpd_regex += r"|([A-ZÊÙÈÀÂÔÎÉÁ] (\. )?)+"              #sigles et acronymes
		self.cpd_regex += r"|((https?:\/\/ )|(www))([\da-z\. -]+) \. ([a-z\. ]{2,6})([\/\w ~=\?\.-]*)*( \/)? "#URLs
		self.cpd_regex += ")"
		self.cpd_regex = re.compile(self.cpd_regex)
		
if __name__ == '__main__':
	lex = DefaultLexer('strong-cpd.dic',entity_file='dico_quan1.json')
	while True: 
		print('ready ?')
		bfr = input()
		lex.set_line(bfr)
		token = lex.next_token()
		while token:
			print(token)
			token = lex.next_token()
  
