#!/usr/bin/python

"""
Module for interpreting first order predicates 
"""
import re
from functional_core import *
from lambda_parser import *
from SPARQLWrapper import SPARQLWrapper, JSON

class WikidataModelInterface(ModelInterface):
    """
    That's a factory generating the quantifier and other logical interpretations specific to Wikidata
    """
    def __init__(self):
        pass
    
    @staticmethod
    def make_quantifier(boundvarname,boundvartype,body,**kwargs):
        """
        This method is meant to be subclassed for working with specific models
        """
        if 'answer_marked' in kwargs:
            return WikiExistentialQuantifier(boundvarname,boundvartype,body,answer_marked=kwargs['answer_marked'])
        else:
            return WikiExistentialQuantifier(boundvarname,boundvartype,body)
            
        
    @staticmethod
    def make_predicate(predname,nargs):
        """
        This method is meant to be subclassed for working with specific models.
        @param predname: the name of the predicate
        @param nargs: the number of arguments to the predicate
        @return a predicate
        """
        return WikidataPredicate(predname,nargs)

    
class WikidataQuery:
    """
    That's a namespace for storing wikidata config params
    """
    ENTITY_PREFIX   = "PREFIX wdt: <http://www.wikidata.org/prop/direct/>"
    PROPERTY_PREFIX = "PREFIX wd:  <http://www.wikidata.org/entity/>"
    ENDPOINT = 'https://query.wikidata.org/sparql'
    MAX_QUERY_RESULTS = 1000

    @staticmethod
    def make_select_query(query_vars,generated_query):
        """
        Adds the header and wraps the generated code in a SELECT clause
        @param query_vars : the variable we seek the assignation for
        @param generated_query: the query code generated
        @return a valid SPARQL query as a string
        """
        return """
        %s
        %s
        SELECT DISTINCT %s WHERE {
            %s
            SERVICE wikibase:label {
               bd:serviceParam wikibase:language "fr" .
            }
        } LIMIT %d
        """%(WikidataQuery.ENTITY_PREFIX,WikidataQuery.PROPERTY_PREFIX,' '.join(['%s'%(v,) for v in  query_vars]),generated_query,WikidataQuery.MAX_QUERY_RESULTS)

    #%(WikidataQuery.ENTITY_PREFIX,WikidataQuery.PROPERTY_PREFIX,' '.join(['%sLabel'%(v,) for v in  query_vars]),generated_query,WikidataQuery.MAX_QUERY_RESULTS)

    @staticmethod 
    def make_count_query(query_vars,generated_query):
        """
        Adds the header and wraps the generated code in a SELECT clause
        that returns a counting result.
        
        @param query_vars : the variable we seek the assignation for
        @param generated_query: the query code generated
        @return a valid SPARQL query as a string
        """        
        return """
        %s
        %s 
        SELECT DISTINCT (COUNT (%s) AS ?count) {
            %s
        } LIMIT %d
        """%(WikidataQuery.ENTITY_PREFIX,WikidataQuery.PROPERTY_PREFIX,' '.join(query_vars),generated_query,WikidataQuery.MAX_QUERY_RESULTS)

    @staticmethod
    def make_ask_query(generated_query):
        """
        Adds the header and wraps the generated code in a ASK clause
        @param query_vars : the variable we seek the assignation
        @param generated_query: the query code generated
        @return a valid SPARQL query as a string.
        """
        return """
        %s
        %s
        ASK {
            %s
        }
        """%(WikidataQuery.ENTITY_PREFIX,WikidataQuery.PROPERTY_PREFIX,generated_query)

    @staticmethod
    def run_query(query_string,answer_vars=None,qtype='ASK',debug=False,timeout=3):
        """
        Connect to the server and run the query.
        @param answer_vars: vars for which we are interested in getting the binding.
        @param query_string : the inner SPARQL code.
        @param qtype: the query type: either ASK or SELECT
        @return a boolean if qtype == ASK , a list of assigned entities otherwise.
        """
        #SELECT QUERY
        if qtype == 'ASK':
            query_string = WikidataQuery.make_ask_query(query_string)
            if debug:
                print('sparql query:',query_string)
            sparql = SPARQLWrapper(WikidataQuery.ENDPOINT)
            sparql.setQuery(query_string)
            sparql.setReturnFormat(JSON)
            results = sparql.query().convert()
            return results['boolean'] 
        elif qtype == 'COUNT':
            if not answer_vars:  #recovery for queries without identified focus
                answer_vars = ['*']
            query_string = WikidataQuery.make_count_query(answer_vars,query_string)
            if debug:
                print('sparql query:',query_string)
            sparql = SPARQLWrapper(WikidataQuery.ENDPOINT)
            sparql.setQuery(query_string)
            sparql.setReturnFormat(JSON)
            results = sparql.query().convert()
            return results['results']['bindings'][0]['count']['value']
        elif qtype == 'SELECT':
            if not answer_vars:  #recovery for queries without identified focus
                answer_vars = ['*']
            query_string = WikidataQuery.make_select_query(answer_vars,query_string)
            if debug:
                print('sparql query:',query_string)

            solutions = [ ]
            try:
                sparql = SPARQLWrapper(WikidataQuery.ENDPOINT)
                sparql.setQuery(query_string)
                sparql.setReturnFormat(JSON)
                sparql.setTimeout(timeout)
                results = sparql.query().convert()
                #extract tuples 
                for binding in results['results']['bindings']:
                    solutions.append( [ (varname,binding[varname]['value'].split('/')[-1]) for varname in binding.keys() ])
            except Exception as e:
                #print('Incoherent query issued')
                pass
            return solutions

class SparqlNameGenerator:
    """
    That's a name generator for generating sparql queries code and helper class for managing variable bindings.
    """
    UNIQUE_IDX = -1
    
    def __init__(self):
        self.bound_names = {}

    def __str__(self):
        return '\n'.join(['%s => %s'%(vname,depth) for vname,depth in self.bound_names.items()])
         
    def copy(self):
        cpy = SparqlNameGenerator()
        cpy.bound_names =  dict([(key,depth) for key,depth in self.bound_names.items()])
        return cpy

    @staticmethod
    def get_unique_varname():
        """
        @return a unique name for a new sparql variable
        """
        SparqlNameGenerator.UNIQUE_IDX += 1
        return '?x%d'%(SparqlNameGenerator.UNIQUE_IDX,)

    def add_new_varname(self):
        """
        Create a new variable name with depth = 0
        """
        newvarname = SparqlNameGenerator.get_unique_varname()
        self.bound_names[newvarname] = 0 
        return newvarname
    
    def items(self):
        """
        @return a list of couples (bound_varname,depth)
        The depth is suitable for use with De Bruijn indexes set on Lambda Variables instances.
        """
        return self.bound_names.items()

    def deepen_indexes(self):
        """
        This makes the depth of all variables increase by 1.
        """
        self.bound_names = dict([(key,depth+1) for key,depth in self.bound_names.items()])

        
class NamingContextWikidata(NamingContext):
    """
    Interpreter name bindings management
    """
    def __init__(self,debug=False):

        super().__init__(debug)
        self.predicates_pattern = re.compile('(wdt:P|wd:Q)[0-9]+')
        
    def get_names(self):
        """
        This inherited function cannot be used with this class
        """
        raise NotImplementedError()

    def is_bound_name(self,name):
        """
        Returns true if this naming context binds this name
        """
        return super().is_bound_name(name) or self.predicates_pattern.match(name) 
        
    def __getitem__(self,key):

        if self.predicates_pattern.match(key):
            A = 1 if key.startswith('wd:Q') else 2
            return WikidataPredicate(key,arity=A)

        return super().__getitem__(key)
    
    def __str__(self):
        return super.__str__() + ' + wikidata names...'

    @staticmethod
    def make_wikidata_builtins_context(debug=False):
        """
        The preferred way to instanciate a naming context.
        It includes a 'wikidata library' of builtins utility functions
        Returns a naming context for builtins functions
        @return a NamingContext
        """
        context = NamingContextWikidata(debug)
        builtins = [ExtAddition(),ExtSubstraction(),ExtMultiplication(),ExtDivision(),WikiAnd(),WikiOr(),WikiNot(),\
                    ExtEqual(),ExtNotEqual(),ExtLess(),ExtLessEq(),ExtGreater(),ExtGreaterEq(),Assignation(),Count()]
        for f in builtins:
            context[f.fun_name] = f
        return context


    
#################################################
# LOGICAL SIDE #

class WikidataPredicate(ConstantFunction):

    def __init__(self,pred_name,arity):
        """
        @param name:the name of the predicate
        @param arity: the number or arguments of the predicate
        """
        pred_argtypes = tuple([TypeSystem.DB_ENTITY] * arity)
        super().__init__(name=pred_name,argtypes=pred_argtypes,ret_type=TypeSystem.BOOLEAN)
        assert(arity <= 2 and arity >= 0)
        self.arity = arity

    def ret_value(self):
        """
        Evaluates the denotation of the predicate.
        This amounts to compute a SPARQL query and return its truth value
        @return a boolean (truth value)
        """
        pass #TODO ??? this method should never be called...
        
    def sparql_value(self,answer_vars,var_bindings):
        """
        This generates a SPARQL query for the predicate
        @param answer_vars : variables whose bindings are answers to the question 
        @param var_bindings: a dict sparql_varname: depth
        @return: a string part of the query
        """
        #TODO ? maybe set var bindings to free vars and return anyway in case of binding failure ??
        if self.arity == 1:
            if self.args_values and isinstance(self.args_values[0],LambdaVariable):
                for sparql_varname,depth in var_bindings.items():
                    if self.args_values[0].is_bound(self.args_values[0].varname,depth):
                        return 'BIND(%s AS %s)'%(self.fun_name,sparql_varname)
        elif self.arity == 2:
            if len(self.args_values) == 2 and isinstance(self.args_values[0],LambdaVariable) and  isinstance(self.args_values[1],LambdaVariable):
                bindings = [None,None]
                for sparql_varname,depth in var_bindings.items():            
                    if self.args_values[0].is_bound(self.args_values[0].varname,depth):
                        bindings[0] = sparql_varname
                    if self.args_values[1].is_bound(self.args_values[1].varname,depth):
                        bindings[1] = sparql_varname
                    if all([b != None for b in bindings]):
                        break
                return ' %s %s %s .'%(bindings[0],self.fun_name,bindings[1])
            
        print('Ooops predicate name generator is broken.')


#These connector classes are meant to replace default boolean functors @see NamingContextWikidata@builtins
class WikiAnd(ConstantFunction):
    """
    Implements logical and
    """
    def __init__(self):
        super().__init__(name="and",argtypes=(TypeSystem.BOOLEAN,TypeSystem.BOOLEAN),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        res = self.args_values[0].ret_value() and self.args_values[1].ret_value()
        return res

    def sparql_value(self,answer_vars,var_bindings):
        """
        This generates a SPARQL query for the AND
        @param answer_vars : variables whose bindings are answers to the question 
        @param var_bindings: a dict sparql_varname: depth
        @return: a string part of the query
        """
        return '\n'.join([self.args_values[0].sparql_value(answer_vars,var_bindings.copy()),self.args_values[1].sparql_value(answer_vars,var_bindings.copy())])

    
class WikiOr(ConstantFunction):
    """
    Implements logical OR
    """
    def __init__(self):
        super().__init__(name="or",argtypes=(TypeSystem.BOOLEAN,TypeSystem.BOOLEAN),ret_type=TypeSystem.BOOLEAN)

        
    def ret_value(self):
        res = self.args_values[0].ret_value() or self.args_values[1].ret_value()
        return res
    
    def sparql_value(self,answer_vars,var_bindings):
        """
        This generates a SPARQL query for the predicate
        @param answer_vars : variables whose bindings are answers to the question 
        @param var_bindings: a dict sparql_varname: depth
        @return: a string part of the query
        """
        return """
               { %s }
                  UNION
               { %s }"""%(self.args_values[0].sparql_value(answer_vars,var_bindings.copy()),self.args_values[1].sparql_value(answer_vars,var_bindings.copy()))


        
class WikiNot(ConstantFunction):
    """
    Implements logical not
    """
    def __init__(self):
        super().__init__(name="not",argtypes=(TypeSystem.BOOLEAN,),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        return not self.args_values[0].ret_value()

    def sparql_value(self,answer_vars,var_bindings):
        """
        This generates a SPARQL query for the predicate
        @param answer_vars : variables whose bindings are answers to the question 
        @param var_bindings: a dict sparql_varname: depth
        @return: a string part of the query
        """
        return 'NEGATION GENERATOR NOT IMPLEMENTED !'

class WikiExistentialQuantifier(ExistentialQuantifier):

    def __init__(self,boundvar_name,boundvar_type,body,answer_marked=False):
        """
        That creates an Existential quantifier term (exists (boundvar_name:boundvar_type) (func_body) )
        @param quant_name: the quantifier name (e.g. 'exists')
        @param boundvar_name: the bounded variable name
        @param boundvar_type: the bounded variable type
        @param body: a lambda term
        @param question: marked (flag indicating whether the variable
        bound by this quantifier is one for which we wanna get the binding.
        """
        super().__init__(boundvar_name,boundvar_type,body)
        self.answer_marked = answer_marked
    
        
    def copy(self,db_update=0,depth=0):
        """
        Performs a deep copy of the term and returns it
        @param db_update: a number with which to update db_indexes
        @return a WikiExistentialQuantifier instance
        """
        return WikiExistentialQuantifier(self.boundvar_name,self.boundvar_type,self.body.copy(db_update,depth+1),self.answer_marked)
        
    def ret_value(self,ret_type='ASK',debug=True):
        """
        This evaluates the whole subformula behind this node against the database
        and returns a boolean (true or false) if there exists an assignment of the variables satisfied by the model.

        In case the subformula has not type 't' this function will fail.
        In this case, this prints an error message and returns False.
        @return a boolean
        """
        sparql_names = SparqlNameGenerator()
        answer_vars  = [] 
        sparql_query = self.sparql_value(answer_vars,sparql_names)
        return WikidataQuery.run_query(sparql_query,answer_vars=answer_vars,qtype=ret_type,debug=debug)

    def sparql_value(self,answer_vars=None,var_bindings=None):
        """        
        This generates a SPARQL query for the predicate
        @param answer_vars : variables whose bindings are answers to the question 
        @param var_bindings: a SparqlNameGenerator object
        @return: a string being (part of) the query
        """        
        vname = var_bindings.add_new_varname()
        var_bindings.deepen_indexes()

        if self.answer_marked:
            answer_vars.append(vname)
                    
        return self.body.sparql_value(answer_vars,var_bindings)


class Assignation(ConstantFunction): 
    """
    Gets assignations from a logical formula
    """
    def __init__(self):
        #ret type will become a list type in the future
        super().__init__(name="assignation",argtypes=(TypeSystem.BOOLEAN,),ret_type=TypeSystem.DB_ENTITY)

        
    def ret_value(self):
        if isinstance(self.args_values[0],WikiExistentialQuantifier):
            result = self.args_values[0].ret_value(ret_type='SELECT')
            return result
        return []
    
    def __str__(self):
        if isinstance(self.args_values[0],WikiExistentialQuantifier):
            return str(self.ret_value())
        else:
            def pprint_arg(term):
                if isinstance(term,ConstantFunction) and term.is_constant():
                    return str(term.ret_value())
                elif isinstance(term,LambdaVariable):
                    return str(term)
                else:
                    return str(term)
            return '%s(%s)'%(self.fun_name,','.join([pprint_arg(val) for val in self.args_values]))

        
class Count(ConstantFunction):
    """
    This counts the number of results in a query,
    that is the number of distinct assignments that make the query true
    """
    def __init__(self):
        #ret type will become a list type in the future
        super().__init__(name="count",argtypes=(TypeSystem.BOOLEAN,),ret_type=TypeSystem.NUMERIC)

    def ret_value(self):
        if isinstance(self.args_values[0],WikiExistentialQuantifier):
            result = self.args_values[0].ret_value(ret_type='COUNT')
            return result
        return []    

    def __str__(self):
        if isinstance(self.args_values[0],WikiExistentialQuantifier):
            return str(self.ret_value())
        else:
            def pprint_arg(term):
                if isinstance(term,ConstantFunction) and term.is_constant():
                    return str(term.ret_value())
                elif isinstance(term,LambdaVariable):
                    return str(term)
                else:
                    return str(term)
            return '%s(%s)'%(self.fun_name,','.join([pprint_arg(val) for val in self.args_values]))
    
if __name__ == '__main__':
    import sys
    
    wikidata_model = WikidataModelInterface()
    wikidata_names = NamingContextWikidata.make_wikidata_builtins_context(debug=True)
    if len(sys.argv) > 1 :
         source_defines(sys.argv[1],wikidata_names,wikidata_model)

    shell = InteractiveShell(model_interface =  wikidata_model, naming_context = wikidata_names)
    shell.cmdloop()



    
