#! /usr/bin/env python
# -*- coding: UTF-8 -*-

"""
Dummy lexer, this is basically a translation with slight variations of the C++ version used in nlp-toolbox
"""
import re
import json

from lambda_parser import FuncParser
from functional_core import TypeSystem
from wikidata_model import WikidataModelInterface,NamingContextWikidata
import string
import datrie
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
	
	def __init__(self,cpd_file,entity_file=None,trie_file=None):
		self.compile_regexes()
		self.compile_cpd(cpd_file)
		self.mwe_regex = None
		self.compile_mwe(entity_file,trie_file)

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
			match = self.mwe_regex.longest_prefix(self.inner_bfr[self.idx:], u"not found noooooo")
			if match!="not found noooooo":
				match = self.mwe_regex.longest_prefix(self.inner_bfr[self.idx:])
				token       = self.inner_bfr[self.idx:( self.idx + len(match) )]
				self.idx    = ( self.idx + len(match) )
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

	def compile_mwe(self,entity_file,trie_file,max_vocab_size=4459135):
		# max_vocab_size=4459136
		self.entity_dict = {}
		if entity_file:	
			print(datetime.datetime.now())
			istream = open(entity_file)
			#keylist = {}
			idx = 0
			line = istream.readline()
				
			if not trie_file:
				#list_characters = ["\uc608", "{", "\u5cb8", "\u1ef1", "\u0466", "\u733f", "\u0540", "\u0b24", "\u00f6", "\u03a6", "\uc2ec", "\u013a", "\u6ca2", "\u2078", "\u0644", "\u03b1", "\u1049", "\u6590", "\u6a29", "\u7433", "\u0918", "\u9f4a", "\u09be", "\u0a6e", "\u500d", "4", "\u5075", "\u8d24", "\u5389", "\u8a9e", "\u9645", "\u0bc2", "\u05e2", "\u671d", "\u0101", "\u0c6d", "\u0443", "\u1370", "\u9042", "\u0bee", "\u0112", "\u200f", "\uac74", "\uc9c4", "\uc601", "\uc0c1", "\u30df", "\uc120", "\u68da", "\u03c9", "\u0e43", "\u094d", "a", "\u00fa", "\u049b", "B", "\u0638", "\u7dd2", "\u0e38", "\u00ea", "\u016b", "\u00d0", "\u1e93", "\u3080", "\ubc15", "\u9593", "\u0728", "\u0572", "\u00b0", "\u76f8", "\u96d1", "\u0666", "\u0582", "\u063a", "\uc6c5", "\u1010", "\ud574", "n", "\u0e19", "\u201b", "=", "\u0930", "\u2461", "\u82d7", "\uaddc", "\u03d8", "\u1228", "\u02ee", "\u3070", "\u02cb", "\ufeff", "\u5b88", "\u6210", "\u0b99", "\u53b2", "\u0177", "\u1ec1", "\u0117", "\ubaa8", "\u5927", "\u738b", "\u0448", "\u090f", "\u5b5d", "\u62bc", "\u0648", "\ub958", "\u9b6f", "\uc6b1", "\u00e1", "\u2d4e", "\ucca0", "\uff0c", "\u0270", "\ud0dc", "\u8c4a", "\u798f", "\u0126", "\u53f7", "\u0cec", "\u80b2", "\u8c37", "\u89c2", "\u305b", "\u00e0", "\u5cb3", "\u091b", "\u013e", "\u013c", "\u00b5", "\u0924", "\u0787", "\u0fb3", "\u540d", "\u01f4", "\u130d", "z", "\u057f", "\u00fe", "\u2015", "\u1ed1", "\u308d", "\u522b", "\u308a", "\u7f16", "\ub9bc", "\u7d17", "\u0651", "\u5b50", "\u0169", "\u0449", "\u7267", "\u03a3", "\u822a", "\u519b", "\u6728", "\u969c", "\u6e21", "\uc21c", "\u092c", "\u6148", "\u5e9c", "\u1371", "\u203f", "\u8ce6", "\ud638", "h", "\u2c94", "\uc2dc", "\u9451", "y", "\u7cb5", "\u03b4", "\u12a2", "\u7f8e", "\u4f34", "\u043e", "\u7af9", "\u012d", "\u6182", "\u021f", "T", "\u1ca5", "\u3053", "\u90e1", "E", "\u5009", "\u1e2b", "\u0179", "\u85e4", "\u56fd", "\u7834", "\u0433", "\u062f", "\u0985", "\u0645", "W", "\u4e43", "\u0160", "\u0567", "\u1ecf", "\u5c9b", "\u9ad8", "\u057d", "\u096d", "\u5bfa", "\u06f9", "\u0ed6", "\u0308", "\u679d", "\u0100", "\uc7ac", "\u0bcd", "\u01d4", "\u0625", "\u0c6e", "\u0932", "\u0f58", "\u0144", "\u4e03", "\u68df", "\u10d8", "\u51a8", "\u8cab", "\u0402", "\u0418", "s", "\u07a8", "\u1828", "\u304a", "\u0431", "\u03d9", "\u20ac", "\u1e35", "\u0629", "\u5149", "\u30d6", "\uc544", "\u8302", "\u7f6e", "\u61b2", "\u211a", "\u5b89", "\u2200", "\u03af", "\u5e83", "\u05d8", "\u1edf", "\u0564", "\u6253", "\u00d2", "\u09ac", "o", "\u2220", "\u2c97", "\u025b", "\u65c5", "\u306c", "\u0623", "\u4faf", "m", "\u0641", "\u0cef", "\u4e1a", "\u2c87", "\uc724", "\u0bef", "\u09b8", "\u5fc3", "A", "\u043d", "\u4eca", "\u0622", "\u5712", "R", "\u014e", "\u10d6", "\u0632", "\u4fa8", "\u0b30", "\u0578", "\u02c8", "\u2c81", "\u212f", "J", "\u3075", "\u9808", "\u0e57", "\u732e", "\u1335", "Q", "\u6c11", "\u00b2", "\u0436", "\u1eef", "\u6f5f", "\u0451", "\u1ee9", "\u0e4c", "\u0155", "\u12ee", "\u0907", "$", "\u00e7", "\u0574", "\u30cf", "\u963f", "\u4e2d", "\u0905", "\u83ca", "\u71b1", "\u0111", "\u8389", "\u6216", "\u016a", "\u0b6c", "\u5fd7", "\u7de8", "\u65bd", "\u0300", "\u4e61", "\uc778", "\u200e", "\u677f", "\u0141", "\u1ebd", "\u6851", "\u0e56", "\u06f6", "\u72e9", "\u034f", "\u0437", "\u0422", "\u0537", "\uad6d", "\u9152", "\u078a", "\u938c", "\u00c2", "\uba85", "\u3076", "\u67f3", "\u0219", "\u1e47", "\u5b9f", "\u182d", "\u52dd", "\u0636", "\u8fbb", "q", "\u5e1d", "\uc624", "\u9806", "\u266f", "\u8a69", "\u00b1", "\u6d25", "l", "\u6e56", "\u697d", "\uc6a9", "\uc6d0", "#", "\u043a", "\u2661", "\u57a3", "\u690d", "\u1ca8", "\u0bb0", "\u078c", "\u2014", "\u0419", "\u9707", "\u307b", "\u5d0e", "\u82b3", "\u01e7", "\u09ec", "\ua658", "\u767d", "\u5f26", "\u03c7", "\u0438", "\u5bb6", "\ud658", "\u6bd2", "\u03c6", "\u0d24", "\u4eac", "\u306f", "Y", "\u0e58", "\u03ea", "\u05e9", "\u30eb", "\u00a1", "\u541b", "\u013b", "\u5341", "\u1c92", "\uc5e0", "\u71d2", "\u5229", "\u00fc", "\u4e0b", "\u1edb", "\u039a", "\uc790", "\u09a8", "\u7a32", "\u0f0b", "\u2135", "\u0161", "\u262e", "\u6e6f", "\u9274", "\u0415", "\u831c", "\u9928", "\u0bbf", "\u9b54", "\u017d", "\u5efa", "\u7d00", "\ubc31", "\u030c", "\u044c", "\u031c", "\u0576", "\u305d", "\u983c", "\u6ce2", "\u81e8", "\u0e41", "\ua65a", "\u6dbc", "\ua65b", "\u042e", "\u5199", "\u54b2", "\u672b", "\u0652", "\u00f1", "\u2020", "\u4e94", "\ufb02", "\u81f4", "\u6797", "\u00cd", "\u77e2", "\u5316", "\u010d", "\u5411", "\u2c82", "\u305f", "\u0abe", "\u674e", "\u2c93", "\u123a", "\u0a6d", "\u5b99", "\ud61c", "~", "\u00cf", "\uc560", "\u0107", "\u0446", "\u6b66", "\u516c", "\u8239", "\u53cb", "\u10db", "-", "\ubcd1", "\u02ba", "\u0116", "\u266d", "\u12c8", "\u0915", "\ub300", "\u9ed2", "\uc2b9", "\u5973", "\u30c3", "\u30e6", "\u542f", "\u3052", "\u51db", "\u039f", "\u07a6", "\u016c", "\u014d", "\u0b9c", "\u054d", "\u1c94", "\u30d2", "\u07b0", "\u7530", "\u5b87", "\u182f", "\u01c3", "\u5e02", "\u02c9", "\u01fd", "\u3082", "\u0e2d", "!", "w", "\u046b", "\u658e", "\u52a0", "\u6c5f", "\u0721", "\u01f5", "\u0542", "\u2c9b", "\u1ca1", "\u09cd", "\u1e6f", "\u30b0", "\u0f72", "\u0bed", "\uc885", "\u6708", "\ud55c", "\u91ca", "\u00c0", "\u0e32", "\u98ef", "\u69d9", "\u6e05", "\u057c", "\u30e3", "\u7cfb", "\uc900", "\u685c", "\u6975", "\u7a76", "^", "\u5c4b", "\u30d9", "c", "\u6bdb", "\u056c", "\u7531", "\u53f3", "\u8ca9", "\u0942", "\u0ab0", "\u00b3", "\u5e78", "\u4e09", "\u6e80", "\u06cc", "\u02b7", "\u05e0", "\u00f2", "\u306e", "\u5201", "\u20a3", "\u06af", "\u576a", "\u0919", "\u8427", "\u2c91", "\u4f0a", "\u6211", ">", "\u2161", "\u0259", "\u00f5", "C", "\u05d3", "\u958b", "\u1ef9", "\u30ba", "\u03e8", "\u0299", "\u5800", "\u072a", "\uc6b0", "\u05e6", "\u516b", "\u3094", "\u0928", "\u65b9", "\u9234", "\u00de", "\u00ae", "\u1ead", "\u03a5", "@", "\u8336", "\u2c9e", "\u0f4f", "\u718a", "\u0aee", "\u1c90", "\u0123", "\u30c9", "\u10e3", "\u1e43", "\u5e84", "\u09c7", "\u0e07", "\u03ed", "\u017f", "\u1047", "\u03c5", "\u0191", "\ud130", "\u2010", "\u1c9d", "\u3058", "\u0d02", "\u30c7", "\u09ad", "\u9023", "\u79cb", "\u1eeb", "\u6e90", "\u8597", "\u7edf", "\u013d", "\u30ec", "\u9769", "\u30c0", "\u0902", "\u0441", "\u884c", "\u652f", "\u0434", "\u6734", "\u04d5", "\u1ee7", "\u0162", "\u8499", "\u0454", "\ub77c", "\u30a4", "\u2642", "\u091a", "\u00ed", "S", "\u05d1", "\u7ae0", "\u057a", "\u045e", "\u5317", "\u2c9c", "\u9759", "\uc131", "\u045b", "\u307e", "e", "\u8b19", "\ub9cc", "\u7be0", ":", "\u00db", "\u547d", "\u6bce", "\u6238", "\u043c", "\u046d", "\u1e0f", "\u7c73", "\uc815", "\u1ed5", "\u012b", "\u81ea", "\ub4dc", "\u02d0", "\u7cbe", "\u6cf0", "\u011b", "\u1e6c", "\u9999", "\u0b87", "\u0ba8", "\u05b4", "\u30e4", "\u092f", "\u5b66", "\u2606", "\u2171", "\u4e8c", "\u03a9", "\u4e0e", "\u03bc", "\u00dd", "\u7b19", "\u5fb3", "\u053f", "\u5171", "\u76ae", "\ube48", "j", "\u0e40", "\u103c", "\u90b4", "\u3048", "\u4ec1", "\ua65d", "\u0421", "\u4e07", "\u00d9", "\u675c", "\u9148", "\u091d", "\u6703", "\u5f18", "\u093f", "\u0935", "\u95a9", "\u0639", "Z", "\u5948", "\u0f29", "\u03c0", "\ub9e4", "\u1ecd", "\u0159", "\u09b0", "\u674f", "\u05e8", "\u698e", "\u0575", "\u5a18", "\u2c98", "\u05d4", "\u30e1", "\u4e00", "\u30ce", "\u0791", "\u6c38", "\u6dfb", "\u2c92", "\u01a9", "\u5f71", "\ub808", "\u0626", "\u3072", "\u0640", "\u0171", "\ub098", "\uc5d4", "\u2c83", "\u00c7", "\u0136", "\u015f", "\u017e", "\u1e37", "\u1ecb", "\u03bd", "\u3050", "\uce58", "\u096c", "\u0263", "\u043f", "\u0643", "\u0627", "\u00f7", "\u096e", "\u767a", "\u3079", "\u4eee", "\u5439", "\ufb01", "\u96e8", "\u7802", " ", "\u529f", "\u2143", "\u0aa4", "\u8987", "\u77f3", "\u671b", "P", "\u5ca9", "\u6dfa", "\u7f29", "\u76ca", "\u044a", "\u5cf6", "\u03be", "\u5f25", "\u3086", "\u7532", "\u4ef2", "\u0bec", "\u0c3e", "\u0410", "\u221a", "\ufe20", "\u0a30", "\u0119", "\u80fd", "\u5d14", "\u6817", "\u7586", "\u7acb", "\ub85c", "\u2640", "\u00c9", "\u018a", "\u03a1", "\u1e6d", "\u02bb", "\u0130", "\u8535", "\u59bb", "\u6de1", "}", "\u1ee3", "\u771f", "\u03cd", "\u06f8", "\uad6c", "\u3085", "\u0650", "\u0937", "\u10d2", "\u0121", "\uacbd", "\u0ba4", "\u6656", "\u0584", "\u908a", "\u03c3", "\u015b", "\ud14c", "\u2cc1", "\u07aa", "\u3054", "\u86ef", "\u0456", "\u0e42", "\u793e", "\u00f0", "\u03b5", "\u10e0", "\u301c", "\u6c60", "\u1e24", "\u6842", "\u10ea", "\ua65c", "%", "\u056e", "\u1e49", "\u1014", "\u062c", "\u0940", "\u0e04", "\u6559", "\u00c8", "\u0414", "\u0457", "\u00e9", "\u103a", "\u795e", "\u1f41", "\u5f90", "\ud6a8", "\u00ce", "\uad11", "\u02bc", "\u12f5", "\u099c", "\u4f38", "\u0122", "\u6761", "\u012a", "\u307c", "|", "\u091f", "\u062a", "\u0939", "U", "\u06f7", "\uc5f0", "\u6cc9", "\u2032", "\uc694", "\u0469", "\u03b3", "\u5ca1", "\u76db", "\u732b", "\u1e7f", "\u04a7", "\u3042", "\u5219", "\u046a", "\uc11d", "\u0329", "\u10e4", "\u091e", "\u65b0", "\u0c6c", "\u0145", "\u6770", "\u00dc", "\u9060", "\u73af", "\u021a", "\u7269", "\u0e22", "\u0e01", "\u7814", "\u136f", "\u4e7e", "\u95a2", "\u134a", "\u0303", "\u5553", "\u0439", "\u4fdd", "\u4f9d", "\ucd5c", "\uc138", "L", "\u597d", "\u8584", "\uc11c", "\u0468", "\u0947", "\uc219", "\u0445", "\u00e6", "\u0a6f", "\u062e", "\u032a", "\u9e7f", "\u03e9", "\u0165", "\u1ea5", "\u010e", "\u044e", "\u041d", "\u0459", "\u30bf", "\u0127", "\u9f8d", "\u0401", "\u571f", "\u66f2", "\ube14", "g", "\u03bf", "\u602a", "\u0e23", "\u044f", "\u0129", "\u592a", "\u0633", "\u0ced", "\u092e", "\u0bb2", "\u01ea", "\uff1a", "\u0467", "\u01c1", "\u03ce", "\u534d", "\u30ca", "\u1f08", "\u210d", "\u583a", "\u6c34", "\u304b", "\u1820", "\u0628", "\u3055", "\u3067", "\u211d", "\u8c9e", "\u4eae", "\u1eaf", "\u1ea3", "\u1e92", "\u038e", "\u00ec", "\u3066", "\u2095", "\u6d66", "\u1f25", "\u0a2d", "\u200b", "\u00e8", "\u1e63", "\u10d9", "\u5c3e", "\u4efb", "\u016d", "\u03d0", "v", "\u0565", "\u2136", "\u264b", "\u7b52", "\u9f13", "\u0394", "\u041e", "\u00b4", "\u30b8", "\u0669", "\u306b", "\u05e1", "\u1e3b", "\u03ac", "\u6d3b", "\u6768", "H", "\u00eb", "\u5929", "\u8fd1", "\u03b2", "\u041f", "\u4eba", "\u91ce", "\u01a1", "\u00ef", "6", "\u677e", "\u1e8f", "\"", "\u2082", "\u0950", "\u064f", "\u016f", "\u6a5f", "\u0f56", "\u054e", "\u201e", "\u591a", "\u0986", "\u8d8a", "\u9803", "\u00ff", "\u12eb", "\u0f28", "\u05d2", "7", "\u5b54", "\ud558", "\u53f2", "\u7279", "\u1c97", "\u0416", "\u0d6e", "\u0427", "\u4e45", "\u539f", "\u017a", "\u592b", "\u041c", "\u8def", "\u1ed3", "\u042f", "\u5218", "\ubb38", "\u2085", "\u1caa", "'", "\u8cc0", "\u9e92", "\uc9c0", "\uc8fc", "\ubcf4", "\u307f", "\u80a5", "\u6751", "\u767e", "\u84ec", "\u00b7", "\u621a", "\u2295", "\u0bbe", "\u0175", "\u5217", "\u9452", "\u017b", "\u304e", "\u0307", "\u0baa", "\ua659", "\u5186", "\u3063", "\uc720", "\u09c1", "\u6d0b", "\u0120", "\u10d1", "\u6e25", "\u0a28", "\u10e2", "\u7a81", "\u6d6e", "\u6e0b", "\u0621", "u", "\u12a5", "\u0d28", "\uc2e0", "\u4e16", "\u4f50", "\u05d6", "\u897f", "\u182a", "\u0424", "\u8d77", "\u049a", "\u9577", "N", "\u2011", "\u03b9", "\u3059", "\u010c", "\u1e29", "\u078b", "\u031e", "\u6881", "\u09bf", "\u90ce", "\u0f27", "\u0458", "\u1c9a", "\u9662", "\u0570", "\u5805", "\u8ef8", "\u3060", "\u2d3b", "\u7b95", "\u015e", "\u10d7", "\u030b", "\u0147", "\u014b", "/", "\ufb06", "\u0398", "\u9b31", "\u524a", "d", "x", "\u90a3", "\u1822", "\u017c", "\u5dde", "\u00c1", "\u0d35", "\u8f66", "\u5b97", "F", "\u4f73", "\u0aad", "\u062d", "k", "\u742a", "\u096f", "\u0bc8", "\u2d5c", "\uac08", "\u898b", "\u03a8", "\u1eb5", "\u1813", "\u856d", "\u5408", "\u9cf4", "\u3062", "\u042d", "\u1ebf", "\u03c4", "\u0430", "\u5ba4", "\u30cb", "\u67cf", "\u0412", "\u5100", "\u200c", "\u7121", "\u00fb", "\u6625", "\uc625", "\u1ebc", "\u0b2d", "\u1015", "\u7f57", "\u99ac", "\u756a", "\u03de", "\u0a2e", "\u9ce5", "\u6edd", "\u2c96", "\uba3c", "t", "\u2022", "\u7b20", "\u1d50", "\u00a9", "\u2080", "\u0106", "\u2c80", "\ud6c8", "\u5c71", "\u05da", "\u5996", "\u0444", "\u12f0", "\u00d6", "\u0132", "\u6cb3", "\u092a", "\u91cc", "\u68a8", "\u69d8", "\u8033", "\u88cf", "\u0146", "\u00bc", "\u2c90", "\u5f8c", "\u5bae", "\u043b", "\u10dc", "\u00d7", "\u304c", "\u02b9", "\u8494", "\u0d30", "\u2202", "\u0e02", "\u8f1d", "\ud615", "\u0aec", "\u95ee", "\u53c8", "\u0148", "\u056f", "\u771e", "\u1031", "\u01dd", "\u3081", "\u5e2b", "\u305e", "\u056b", "\u0c4d", "\u010f", "\u50b3", "\u0142", "\u0395", "\u0710", "\u0e48", "\u73e0", "\u624b", "\u6771", "\u0d4d", "O", "\u30c6", "\u0118", "\u0667", "\u9053", "\uc548", "\u1e53", "\u0151", "\uc870", "\u00f3", "\u0580", "\u1edd", "\u0a6c", "\u82b8", "\u0440", "\u6fa4", "\u8f2a", "\u1308", "K", "\u0ed8", "\u2d4d", "\u524d", "\u03eb", "\u2153", "\u0428", "\u3089", "\u0e1e", "\u8d64", "\u0393", "\u00ca", "\u30fc", ",", "\u06c7", "\u0a39", "\u1235", "\u3056", "\u05e4", "\u4f5b", "\u2081", "\u039d", "\u653f", "\u653e", "\u10dd", "\u0d41", "\u10d4", "\u044b", "\u1046", "\u82b1", ".", "\u59b9", "\u0b6e", "\u57ce", "\u91d1", "\u03b8", "D", "\u2651", "\u3064", "\u2cc0", "\u09ed", "\u9648", "\u0923", "\u63a2", "\u02bf", "\u0533", "\u01e6", "\u5c11", "\u03ad", "\u5e81", "\u1c9c", "\u308f", "\ucc3d", "\u89e3", "\u97d3", "\u014c", "9", "\u015a", "\u0917", "\u4e4b", "\u9685", "\u2234", "\u0e44", "\u4e38", "\u5742", "\u660c", "\u30af", "\u3073", "\u3069", "\u7e54", "\u5f53", "\u7389", "\u1824", "\u0718", "M", "\u00a5", "\u01da", "\ud76c", "\u0423", "\u1ed9", "\u3087", "\u10ef", "\u0562", "\u5b85", "\u03b7", "\u987a", "\u0113", "\u71d0", "\uac00", "\u585a", "\u30ea", "\u046c", "\uc740", "\u53f8", "\u091c", "\u9673", "\u3051", "\u2115", "\u0218", "\u3046", "\u0b6f", "\u1cae", "\u02b2", "\u8d85", "\u5965", "\u2d5b", "\u6d77", "\u83f2", "\u03bb", "\u00fd", "\u09ef", "\u3044", "\u03ae", "\u698a", "\u0642", "\u00ad", "\u0577", "\u570b", "\u2013", "\u092b", "\u5bcc", "\u8352", "\u7aaa", "\u7d30", "\u7fbd", "<", "X", "\u1eb7", "\u514b", "\u30ab", "\u7d19", "\u8d4b", "\uae30", "\u0301", "\u30ac", "\u6d45", "p", "\u03ba", "\u093e", "\u05d7", "\u1c9b", "\u044d", "\u011f", "\u05dd", "\u6e7e", "\u672c", "\u0c30", "\uc2ac", "\u04e9", "\u7560", "\u011d", "\u30f4", "\u0631", "\u8449", "\u9127", "\u30e9", "\u00d1", "\u0417", "\u0a26", "\u89d2", "\u30de", "\u0c24", "i", "\u0cee", "\u0304", "\u2194", "\u05bc", "\u6a2a", "\ub799", "\u0668", "\u00f9", "\u6d5c", "\u6885", "\u0452", "\u7406", "\u305a", "\u01d0", "\u4ee3", "\u03a4", "\u2075", "\u4e01", "\u8ce2", "\u8a2d", "\u136e", "\u0e17", "\u4e3a", "\u7a46", "\u1ec7", "\u0e2f", "\u5bfe", "\u0f71", "\u09a4", "\uc2dd", "\u90e8", "\u548c", "\u00aa", "\u5343", "\u0635", "\u00df", "\u30e0", "`", "\u049f", "\u05d9", "\uc77c", "\u5761", "\u8d5b", "\u00af", "\u04d8", "\u03c8", "\u039c", "\u6709", "5", "\u0b95", "\u5185", "\u5410", "\u00e4", "\u00ee", "\u0d2a", "\u0561", "1", "\u83c5", "\u9418", "\u4f8d", "\u7d50", "\u7aef", "\u6b63", "\u05d5", "\u6642", "\u5d8b", "\u1f2d", "\uc218", "\u067e", "\u0926", "\u805e", "\uc774", "\u5e73", "\u2460", "\u01b0", "\ubbfc", "\u1e7e", "\u51fa", "\u7a7a", "\u0432", "\u0150", "\u69fb", "\u8868", "\u0411", "\u0c6f", "\u1ea9", "\u639b", "\u53e4", "\u2c9f", "\u2665", "f", "\u702c", "\u65e9", "\u00f8", "\u5de5", "\u30a2", "2", "\u6717", "\u010b", "\u69cb", "3", "\u0326", "\u10d3", "\u03a0", "\u0aed", "\u1e62", "\u0d6c", "\u0ed9", "b", "\u30bc", "\u00f4", "\ufe21", "\u0105", "\u8aa0", "\u308b", "\u7551", "\u554f", "\u6cb9", "\u0283", "\u0d3f", "\uc7a5", "\u12cd", "\u30ed", "\u00b9", "\u00d3", "\u0a4b", "\u8521", "\u1c95", "\u543e", "\u5409", "\u221e", "\u6faa", "\u2c99", "\u3084", "\u0936", "\u0392", "\u949f", "\u758b", "\u52d2", "\u1c98", "\u559c", "\u9727", "\u0192", "\ubbf8", "\u042a", "\u030d", "\u07ae", "\u0a24", "\ub0a8", "\u2609", "\u05e7", "\u0637", "\u0e59", "\u05d0", "\u1ee5", "\u2c9d", "\u01ce", "\u03c2", "\u053c", "\u0406", "\u03ec", "\u05ea", "\u3065", "\u4f0f", "\ub298", "\u8654", "\u09aa", "\u00e2", "\u0b6d", "\u7167", "\u0391", "\u0425", "\u0152", "\uc190", "\u9089", "\u5916", "\u0c2d", "\u5730", "\u30aa", "\u10d5", "\u0413", "\u03c1", "\u041b", "\u2c9a", ";", "\u0426", "\u1e8b", "\u0257", "\u071d", "\u0b3e", "\u90e6", "\u30d3", "\u2d4f", "\u05de", "\u0785", "\u0103", "\u6804", "\u0d6f", "\u534e", "\u041a", "\u5ddd", "\u00c5", "\u660e", "\u5869", "\u5dfb", "\u10da", "\u2192", "\u865f", "\u3083", "\u014f", "\u09ee", "\u03cc", "\u039e", "\u05dc", "\ud654", "\u3061", "\u05df", "\u4f1d", "\u0435", "\u021b", "\u53e3", "\u9ebb", "\u0315", "\u0baf", "\u79c1", "0", "\u533a", "\u1ef3", "\u100a", "\ud2b8", "\u2124", "\u7f85", "\u10eb", "\u79e6", "\u30d1", "\u00d8", "\u1eb1", "\u0158", "\u4e39", "\u0563", "\u018e", "\u962a", "\u0109", "\u304d", "\u00be", "\u0110", "\u01c0", "\u7d0d", "\u01eb", "\u517c", "\u5ead", "\u8272", "\u667a", "\u6e2f", "\u04d9", "\u1048", "\u30a6", "\u1ec5", "\u0aef", "\u10e1", "\u0a3e", "\u6c7d", "\u58eb", "\ud2f0", "\u6589", "\u0331", "\u1ea7", "\u0173", "\u1e0d", "\ub3d9", "\u00ba", "V", "\u6749", "\u96a0", "\u0634", "\u182c", "\u68ee", "\u0531", "\u8af8", "\u0404", "\u062b", "\u7a0b", "\u67f4", "\u0921", "\u7b49", "\u5ec9", "\u0583", "\u092d", "\u89aa", "\u0442", "r", "\u1f00", "\u751f", "\u00d4", "\u53f0", "\u4e95", "\u5f13", "\u4e0a", "&", "\u98a8", "\u3093", "\u102c", "\u0d6d", "\u30b9", "\u6587", "\uc18c", "\u10e5", "\u96c5", "\u01d2", "\u6962", "\u6df1", "\u6cbb", "\u057b", "\u0f26", "\u1f49", "\u07a7", "\u6bc5", "\u0397", "\u2605", "\u306d", "\u5433", "\u0131", "\u9ece", "\u10e8", "\u2c95", "\u30b3", "\ud604", "\u057e", "\u8fba", "\u30f3", "\u1c91", "\u1d49", "\u0647", "_", "\u10ee", "\u5b5f", "\u00c4", "\u0f60", "\ub8e1", "\u05db", "\u2c86", "\u00c3", "\u00e5", "\u6afb", "\u2103", "\u0995", "\u3057", "\u22c5", "\u03df", "\u1ec9", "\u0429", "\u656c", "\u2212", "\u5b6b", "\u304f", "\u8429", "\u1e25", "\u3068", "\u5bb0", "\u5e06", "\u30a8", "8", "\u05b8", "\u00bd", "\u02b0", "\u0ed7", "\u2102", "\u0447", "\u06a9", "\u5357", "\u65e5", "\u1e2a", "\ucd98", "\u1293", "\u207a", "\u1e5f", "\u0b9a", "I", "\u6a4b", "\u00da", "\u1275", "\u00d5", "\u00c6", "\u5b57", "\u6f64", "\u03a7", "\u10d0", "\u661f", "\u30bd", "\u306a", "\u0137", "\u0f63", "\u02be", "\u064a", "\u0420", "\u00e3", "\u6893", "\u0795", "\u0e27", "\u0312", "\u8aac", "\u9752", "\u039b", "\u3088", "\u263c", "\u09b2", "\u0133", "\u0108", "\u5c0f", "\u0646", "\u5c0b", "\u5eab", "\u0569", "\u1ea1", "\u82e5", "\u7063", "\u0a38", "\u502b", "\u00a7", "\u0544", "\u826f", "\ud53c", "\u03b6", "\u5143", "\u018f", "G", "\u30c8", "\u8f9e", "\uff06", "\u0163", "\u0399", "\u5834", "\u5cf0", "\ucc44", "\u30c4"]
				list_characters = ['\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006', '\u0007', '\u0008', '\u0009', '\u000a', '\u000b', '\u000c', '\u000d', '\u000e', '\u000f', '\u0010', '\u0011', '\u0012', '\u0013', '\u0014', '\u0015', '\u0016', '\u0017', '\u0018', '\u0019', '\u001a', '\u001b', '\u001c', '\u001d', '\u001e', '\u001f', '\u0020', '\u0021', '\u0022', '\u0023', '\u0024', '\u0025', '\u0026', '\u0027', '\u0028', '\u0029', '\u002a', '\u002b', '\u002c', '\u002d', '\u002e', '\u002f', '\u0030', '\u0031', '\u0032', '\u0033', '\u0034', '\u0035', '\u0036', '\u0037', '\u0038', '\u0039', '\u003a', '\u003b', '\u003c', '\u003d', '\u003e', '\u003f', '\u0040', '\u0041', '\u0042', '\u0043', '\u0044', '\u0045', '\u0046', '\u0047', '\u0048', '\u0049', '\u004a', '\u004b', '\u004c', '\u004d', '\u004e', '\u004f', '\u0050', '\u0051', '\u0052', '\u0053', '\u0054', '\u0055', '\u0056', '\u0057', '\u0058', '\u0059', '\u005a', '\u005b', '\u005c', '\u005d', '\u005e', '\u005f', '\u0060', '\u0061', '\u0062', '\u0063', '\u0064', '\u0065', '\u0066', '\u0067', '\u0068', '\u0069', '\u006a', '\u006b', '\u006c', '\u006d', '\u006e', '\u006f', '\u0070', '\u0071', '\u0072', '\u0073', '\u0074', '\u0075', '\u0076', '\u0077', '\u0078', '\u0079', '\u007a', '\u007b', '\u007c', '\u007d', '\u007e', '\u007f', '\u0080', '\u0081', '\u0082', '\u0083', '\u0084', '\u0085', '\u0086', '\u0087', '\u0088', '\u0089', '\u008a', '\u008b', '\u008c', '\u008d', '\u008e', '\u008f', '\u0090', '\u0091', '\u0092', '\u0093', '\u0094', '\u0095', '\u0096', '\u0097', '\u0098', '\u0099', '\u009a', '\u009b', '\u009c', '\u009d', '\u009e', '\u009f', '\u00a0', '\u00a1', '\u00a2', '\u00a3', '\u00a4', '\u00a5', '\u00a6', '\u00a7', '\u00a8', '\u00a9', '\u00aa', '\u00ab', '\u00ac', '\u00ad', '\u00ae', '\u00af', '\u00b0', '\u00b1', '\u00b2', '\u00b3', '\u00b4', '\u00b5', '\u00b6', '\u00b7', '\u00b8', '\u00b9', '\u00ba', '\u00bb', '\u00bc', '\u00bd', '\u00be', '\u00bf', '\u00c0', '\u00c1', '\u00c2', '\u00c3', '\u00c4', '\u00c5', '\u00c6', '\u00c7', '\u00c8', '\u00c9', '\u00ca', '\u00cb', '\u00cc', '\u00cd', '\u00ce', '\u00cf', '\u00d0', '\u00d1', '\u00d2', '\u00d3', '\u00d4', '\u00d5', '\u00d6', '\u00d7', '\u00d8', '\u00d9', '\u00da', '\u00db', '\u00dc', '\u00dd', '\u00de', '\u00df', '\u00e0', '\u00e1', '\u00e2', '\u00e3', '\u00e4', '\u00e5', '\u00e6', '\u00e7', '\u00e8', '\u00e9', '\u00ea', '\u00eb', '\u00ec', '\u00ed', '\u00ee', '\u00ef', '\u00f0', '\u00f1', '\u00f2', '\u00f3', '\u00f4', '\u00f5', '\u00f6', '\u00f7', '\u00f8', '\u00f9', '\u00fa', '\u00fb', '\u00fc', '\u00fd', '\u00fe', '\u00ff']
				self.mwe_regex = datrie.Trie(list_characters)

				while line:
					line    = json.loads(line)
					key     = line['named_entity']         # string of this word
					vallist = list(line['entity_list'])    # all Qs or Ps for this string
					self.entity_dict[key] = vallist
					if ' ' in key:
						self.mwe_regex[key] = idx
					idx += 1
					if idx > max_vocab_size:
						break
					line = istream.readline()

				print(datetime.datetime.now())
				self.mwe_regex.save('my.trie')
				print(datetime.datetime.now())
			else:
				while line:
					line    = json.loads(line)
					key     = line['named_entity']         # string of this word
					vallist = list(line['entity_list'])    # all Qs or Ps for this string
					self.entity_dict[key] = vallist
					idx += 1
					if idx > max_vocab_size:
						break
					line = istream.readline()

				self.mwe_regex = datrie.Trie.load(trie_file)
				print(datetime.datetime.now())

			#self.mwe_regex = sorted(keylist,reverse=True,key=lambda x:len(x))
			#self.mwe_regex = Trie(keylist)

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
	#lex = DefaultLexer('strong-cpd.dic',entity_file='dico_quan1.json',trie_file=None)
	lex = DefaultLexer('strong-cpd.dic',entity_file='dico_quan1.json',trie_file="my.trie")
	while True: 
		print('ready ?')
		bfr = input()
		lex.set_line(bfr)
		token = lex.next_token()
		while token:
			print(token)
			token = lex.next_token()
  
