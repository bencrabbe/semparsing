#! /usr/bin/python

from functional_core import *

import ply.lex as lex
import ply.yacc as yacc
import cmd
import sys
import datetime


class ModelInterface(object):

    """
    Thats a factory used by the parser for generating quantifiers, predicates and other logical interpretations specific to an application
    """

    def __init__(self):
        pass
    
    @staticmethod
    def make_quantifier(boundvarname,boundvartype,body,**kwargs):
        """
        This method is meant to be subclassed for working with specific models
        """
        return ExistentialQuantifier(boundvarname,boundvartype,body)

    @staticmethod
    def make_predicate(predname,nargs):
        """
        This method is meant to be subclassed for working with specific models.
        @param predname: the name of the predicate
        @param nargs: the number of arguments to the predicate
        @return a predicate
        """ 
        return ConstantFunction.make_function(predname,argtypes,TypeSystem.BOOLEAN)



class Lexer(object):

    reserved = {'lambda':'LAMBDA','exists':'EXISTS','@exists':'EXISTSQ','define':'DEFINE','True':'TRUE','False':'FALSE'}
    tokens   = ['IDENTIFIER','DB_IDENTIFIER','ARROW','DOTS','STRING','NUMBER','DATE','LPAREN','RPAREN']+list(reserved.values())
    
    # Simple tokens
    t_LPAREN  = r'\('
    t_RPAREN  = r'\)'
    t_TRUE    = r'True'
    t_FALSE   = r'False'
    t_LAMBDA  = r'lambda'
    t_EXISTS  = r'exists'
    t_EXISTSQ = r'@exists'
    t_DEFINE  = r'define'
    t_ARROW   = r'=>'
    t_DOTS    = r':'

    def __init__(self):
        self.lexer = lex.lex(module=self)
    
    def t_STRING(self,t):
        r'"[^"]*"'
        t.value = t.value[1:-1]
        return t

    def t_DB_IDENTIFIER(self,t):#wikidata entity or property ID
        r'(wd:Q|wdt:P)[0-9]+'
        return t

    def t_DATE(self,t):#Date format is YYYY-MM-DD, ex. 2018-02-03 = Feb 3rd 2018
        r'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        yy,mm,dd = t.value.split('-')
        t.value = datetime.date(int(yy),int(mm),int(dd))
        return t

    def t_NUMBER(self,t):
        r'[0-9]+(\.[0-9]+)?'
        t.value = float(t.value)
        return t

    def t_IDENTIFIER(self,t):
        r'([A-Za-z][A-Za-z0-9]*)|(\+|-|\*|/)|(==|!=|<=?|>=?)'
        t.type = self.reserved.get(t.value,'IDENTIFIER')  
        return t

    # Define a rule so we can track line numbers
    def t_newline(self,t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    # A string containing ignored characters (spaces and tabs)
    t_ignore  = ' \t'

    # Error handling rule
    def t_error(self,t):
        print("Illegal character '%s'" % t.value[0])
        t.lexer.skip(1)

    def tokenize(self,code):
        self.lexer.input(data)
        tok = self.lexer.token()
        while tok:
            #print(tok)
            tok = self.lexer.token()

            
class FuncParser(object):
   
    def __init__(self,naming_context=None, model_interface=None,**kwargs):
        self.lexer = Lexer()
        self.tokens = Lexer.tokens
        self.naming_context = NamingContext.make_std_builtins_context(debug=True) if naming_context == None else naming_context
        self.model_interface = ModelInterface() if model_interface == None else model_interface
        self.parser = yacc.yacc(module=self)
        self.last_defined_macro = None
        self.last_defined_term  = None
        
    def p_parse_program(self,p):
        """
        program : define program
                | term
                | define
        """
        if len(p) == 3:
            p[0] = p[2]
        else:
            p[0] = p[1]

    def p_parse_define(self,p):
        'define : LPAREN DEFINE IDENTIFIER term RPAREN'
        self.last_defined_macro = p[3]
        self.last_defined_term  = p[4] 
        self.naming_context[p[3]] = p[4]

    def p_parse_term(self,p):
        """term : lambda_term
                | quantifier
                | IDENTIFIER
                | literal
                | LPAREN term_list RPAREN """

        if isinstance(p[1],str) and len(p) == 2:#identifier
            name = p[1]
            if self.naming_context.is_bound_name(name):
                p[0] = self.naming_context[name].copy()
            else:
                p[0] = LambdaVariable(name)
        elif p[1] == '(':
            p[0] = p[2]
        else:
            p[0] = p[1]
        #elif isinstance(p[1],LambdaAbstraction):
        #    p[0] = p[1]

    def p_parse_db_id(self,p):#TODO : merge with general identifiers ? (more general)
        """ term : DB_IDENTIFIER """
        predname = p[1]
        if self.naming_context.is_bound_name(predname):
            p[0] = self.naming_context[predname]
        #TODO (in principle not an issue)

                        
    def p_parse_termlist(self,p):
        """term_list : term_list term
                     | term"""
        if len(p) == 3:
            p[0] = LambdaApplication(p[1],p[2])
        elif len(p) == 2:
            p[0] = p[1]
            
    def p_parse_number(self,p):
        'literal : NUMBER'
        p[0] = ConstantFunction.make_constant(p[1],TypeSystem.NUMERIC)
        
    def p_parse_string(self,p):
        'literal : STRING'
        p[0] = ConstantFunction.make_constant(p[1],TypeSystem.STRING)

    def p_parse_date(self,p):
        'literal : DATE'
        p[0] = ConstantFunction.make_constant(p[1],TypeSystem.DATE)
        
    def p_parse_bool(self,p):
        """ literal : TRUE
                    | FALSE"""
        bool_val = True if p[1] == 'True' else False
        p[0] = ConstantFunction.make_constant(bool_val,TypeSystem.BOOLEAN)

    def p_parse_lambda(self,p):
        'lambda_term : LPAREN LAMBDA LPAREN param_list  RPAREN term RPAREN'
        paramList = p[4]
        body      = p[6]
        varname,vartype = paramList.pop()
        T = LambdaAbstraction(varname,vartype,body)
        while paramList:
            varname,vartype = paramList.pop()
            T = LambdaAbstraction(varname,vartype,T)
        p[0]=T

    def p_parse_quantifier(self,p):
        'quantifier : LPAREN EXISTS LPAREN param_list RPAREN term RPAREN'
        paramList = p[4]
        body  = p[6]
        varname,vartype = paramList.pop()
        Q = self.model_interface.make_quantifier(varname,vartype,body)
        while paramList:
            varname,vartype = paramList.pop()
            Q = self.model_interface.make_quantifier(varname,vartype,Q)
        p[0] = Q
        
    def p_parse_marked_quantifier(self,p):
        'quantifier : LPAREN EXISTSQ LPAREN param_list RPAREN term RPAREN'
        paramList = p[4]
        body  = p[6]
        varname,vartype = paramList.pop()
        Q = self.model_interface.make_quantifier(varname,vartype,body,answer_marked=True)
        while paramList:
            varname,vartype = paramList.pop()
            Q = self.model_interface.make_quantifier(varname,vartype,Q,anwser_marked=True)
        p[0] = Q 
        
    def p_parse_params(self,p):
        """param_list : param param_list
                      | param"""
        if len(p) == 2:
            p[0] = [p[1]]
        if len(p) == 3:
            p[0] = [p[1]]+p[2]
        
    def p_parse_param(self,p):
        'param : IDENTIFIER DOTS param_tree'
        p[0] = (p[1],p[3])

    precedence = [ ('right', 'ARROW') ]
    
    def p_parse_param_type(self,p):
        """param_tree : param_tree ARROW param_tree
                      | LPAREN param_tree RPAREN
                      | IDENTIFIER"""
        if len(p) == 2: #ID clause
            p[0] = (p[1],)
        elif p[1] == '(': #( CLAUSE )
            p[0] = TypeSystem.strip_brackets((p[2],)) #remove potential extra ()
        else:             # ARROW CLAUSE
            p[0] = TypeSystem.concat_types(p[1],p[3]) 

    def p_error(self,p):
        print("Syntax error in input!")

    def parse_code(self,codestring):
        """
        This does the job and returns the parsed code as a lambda term
        or a list of \lambda terms.
        """
        return self.parser.parse(codestring,lexer=self.lexer.lexer)

def source_defines(filename,naming_context,model_interface):
    """
    This sources a definition file and returns a Naming Context
    @param naming_context : a naming context
    @return a naming context augmented with the defines in the file.
    """
    parser = FuncParser(naming_context,model_interface)
    istream = open(filename)
    for line in istream:
        line = line.split("#")[0]
        if not line.isspace():
            parser.parse_code(line)
    istream.close()
    return naming_context

class InteractiveShell(cmd.Cmd):
    def __init__(self,model_interface=None,naming_context=None):
        super().__init__()
        self.intro  = """
Welcome to the functional semantic parsing shell.
please enter your terms, definitions or 'q' to quit.

To get matching parens highlights, add the line:
set blink-matching-paren on
to your .inputrc file.
""" 
        self.prompt = '?> '
        self.parser = FuncParser(naming_context,model_interface)
        
    def default(self,line):
        if line[0] == 'q':
            sys.exit(0)
        try:
            T = self.parser.parse_code(line)
            if T != None:
                #print(T)
                ttype = TypeSystem.typecheck(T)
                tval  = T.value()
                print(tval,':',ttype)
        except Exception as e:
            print(e)
        
if __name__ == '__main__' :
    
    shell = InteractiveShell()
    shell.cmdloop()

