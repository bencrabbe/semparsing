#! /usr/bin/python

import copy

class TypeSystem:

    """
    Namespace for typing stuff.
    To be revised in the future, design better type inference with
    limited polymorphism.
    @TODO: the ANY hack should be replaced by (very limited) type equations
    """
    
    NUMERIC   = 'num'
    BOOLEAN   = 't'
    STRING    = 's'
    DATE      = 'd'
    DB_ENTITY = 'e'
    FAILURE   = u'\u22A5' #bottom symbol (least general type)
    ANY       = u'\u22A4' #Top symbol    (most general type)
   
    @staticmethod
    def typenames():
        """
        Returns a set with all accepted typenames
        """
        return set([NUMERIC,BOOLEAN,STRING,DATE,DB_ENTITY,FAILURE,ANY])

    @staticmethod
    def strip_brackets(tuple_type):
        if type(tuple_type) == tuple and len(tuple_type) == 1 and type(tuple_type[0]) == tuple:
            return tuple_type[0]
        return tuple_type

    
    @staticmethod
    def add_brackets(tuple_type):
        if type(tuple_type) != tuple: #an extracted tuple element can become a non tuple 
            tuple_type = (tuple_type,)
        return tuple_type


    @staticmethod
    def concat_types(fun_type,arg_type):
        
        if len(fun_type) == 1:
            return fun_type+arg_type
        else:	  
           return ((fun_type,)+arg_type) 

    @staticmethod
    def deduce_application_type(func_type,arg_type):
        """
        Performs a modus ponens inference for an LambdaApplication term
        @param func_type: the type of a functor
        @param arg_type: the type of an argument
        @return the deduced type
        """
        if arg_type and func_type:
            #print("apply",func_type,' / ',ftype,'==' , arg_type,'>>><<<', TypeSystem.strip_brackets(func_type[1:]))
            if TypeSystem.requires_inference(func_type): #local type inference
                func_type = TypeSystem.type_inference(func_type,arg_type)
                #print('type inference',func_type)
            ftype = TypeSystem.add_brackets(func_type[0]) #an extracted tuple element can become a non tuple
            if ftype == arg_type:
                ret_type = TypeSystem.strip_brackets(func_type[1:]) #the ret_type can be overparenthetized -> strip useless pars if needed
                if ret_type: #the ret_type can be None (if func type was not ... functional)
                    return ret_type
        #application failure
        return TypeSystem.FAILURE
        
    @staticmethod
    def typecheck(term):
        """
        Statically type checks a lambda term and returns its type
        """
        if isinstance(term,LambdaVariable):
            return TypeSystem.add_brackets(term.ttype)
        elif isinstance(term,ConstantFunction):
            return TypeSystem.add_brackets(term.ttype)
        elif isinstance(term,ExistentialQuantifier):
            return TypeSystem.typecheck(term.body)
        elif isinstance(term,LambdaAbstraction):
            body_type     = TypeSystem.typecheck(term.body)
            boundvar_type = term.boundvar_type
            #print("abstract",boundvar_type,' abs ',body_type,'>>><<<',TypeSystem.concat_types(boundvar_type,body_type))
            return TypeSystem.concat_types(boundvar_type,body_type)
        elif isinstance(term,LambdaApplication):
            func_type = TypeSystem.typecheck(term.termA)
            arg_type  = TypeSystem.typecheck(term.termB)
            ret_type = TypeSystem.deduce_application_type(func_type,arg_type)
            return ret_type
            if ret_type == TypeSystem.FAILURE:
                raise TypeError(term.termA,term.termB,func_type,arg_type)
        
        print('oops (type checker broken)')
        return TypeSystem.FAILURE
    
    @staticmethod
    def requires_inference(ttype):
        """
        Checks if there are occurrences of ANY type in type.
        @return True if there is at least one occ of ANY in the typesystem, False otherwise.
        """
        for elt in ttype:
            if  type(elt) == tuple and ( len(elt) >= 1 or type(elt[0]) == tuple):
                if TypeSystem.requires_inference(elt):
                    return True
            if elt == TypeSystem.ANY:
                return True
        return False
    
    
    @staticmethod
    def type_inference(func_type,arg_type):
        """
        That's a minimalistic ad-hoc quickly hacked type substitution procedure for trivial cases where
        types can be inferred locally (a more general type unification procedure is contrary to the current idea).

        => it attempts to replace all the ANY type occurrences in the functor by the type of the argument
        if the type of the argument is ANY -> it fails.
        + restricted to atomic arg types. (might be relaxed with care)
             
        @param func_type:type of the functor
        @param arg_type: type of the argument
        @return a tuple with substitution ANY types
        """
        if type(arg_type) != tuple or len(arg_type) != 1 or type(arg_type[0]) == tuple:
            raise TypeInferenceError(arg_type,'Type inference fails because the supplied argument type is not atomic.')

        if arg_type[0] == TypeSystem.ANY:
            raise TypeInferenceError(arg_type,'Type inference fails because the supplied argument type is left underspecified.')

            
        ret_type = []
        for elt in func_type:
            if elt == TypeSystem.ANY:
                ret_type.append(arg_type)
            elif type(elt) == tuple and ( len(elt) >= 1 or type(elt[0]) == tuple):
                ret_type.append(TypeSystem.type_inference(elt,arg_type))
            else:
                ret_type.append(elt)
        return tuple(ret_type)

        
class TypeError(Exception):
    
    def __init__(self,func_term,arg_term,func_type,arg_type):
        self.func_term, self.arg_term, self.func_type, self.arg_type = func_term,arg_term,func_type,arg_type

    def __str__(self):
        return "Type Error when performing application\nterms: %s / %s\ntypes:%s / %s ==> ??? "%(str(self.func_term),str(self.arg_term),str(self.func_type),str(self.arg_type))

class TypeInferenceError:

    def __init__(self,arg_type,msg):
        self.arg_type = arg_type
        self.msg      = msg

    def __str__(self):
        return msg + '(arg type = %s)'%(str(self.arg_type))

##################################################################
class NamingContext(object):
    """
    This is an execution context for storing function bindings.
    It is meant to manage bindings of built-ins and define(d) functions.
    This currently organizes a trivial flat execution context but could be extended later on if needed.
    """
    def __init__(self,debug=False):

        self.name_dic = {}
        self.debug = debug
        
    def get_names(self):
        """
        This is the set of bound names in this context 
        @returns a set of names
        """
        return set(self.name_dic.keys())

    def is_bound_name(self,name):
        """
        Tells if a name is bound in this context 
        """
        return name in self.name_dic
    
    def __getitem__(self,key):
        return self.name_dic[key]
    
    def __setitem__(self,key,value):
        if self.debug:
            print('binding name %s'%(key))
        self.name_dic[key] = value

    def __str__(self):
        return 'Bound names: %s'%(",".join(self.name_dic.keys()))

    @staticmethod
    def make_std_builtins_context(debug=False):
        """
        The preferred way to instanciate a naming context.
        It includes a 'standard library' of builtins utility functions
        Returns a naming context for builtins functions
        @return a NamingContext
        """
        context = NamingContext(debug)
        builtins = [ExtAddition(),ExtSubstraction(),ExtMultiplication(),ExtDivision(),ExtAnd(),ExtOr(),ExtNot(),\
                    ExtEqual(),ExtNotEqual(),ExtLess(),ExtLessEq(),ExtGreater(),ExtGreaterEq()]
        for f in builtins:
            context[f.fun_name] = f
        return context

class LambdaVariable:

    FREEVAR_IDX = 100000
    
    def __init__(self,varname,ttype=TypeSystem.FAILURE,db_index=FREEVAR_IDX):
        """
        The variable is the basic lambda term.
        @param varname: a string
        @param db_index: De Bruijn Index of the variable
        """
        self.varname,self.ttype, self.db_index = varname,ttype,db_index

        
    def copy(self,db_update=0,depth=0):
        """
        Performs a deep copy of the term and returns it
        @param db_update: a number with which to update db_indexes if the var is free in this term.
        @param depth : the depth of the variable in this term
        @return a LambdaTerm
        """

        if self.db_index-depth > 0 :#if var is free in this term
            return LambdaVariable(self.varname,ttype=self.ttype, db_index=self.db_index+db_update)
        #if var is bound in this term
        return LambdaVariable(self.varname,ttype=self.ttype, db_index=self.db_index)

    
    def bind_var(self,varname,vartype,depth=0):
        """
        This captures variables inside the body and indexes them with
        DeBruijn indexes. Used only at init.
        @param varname: the name of the variable to bind
        @param vartype: the type of the variable to bind 
        @param depth below a quantifier, used for recursive calls
        """
        if varname == self.varname and self.db_index == LambdaVariable.FREEVAR_IDX:
            self.db_index = depth
            if type(vartype) != tuple:
                vartype = (vartype,)
            self.ttype    = vartype
                                    
    def is_bound(self,varname,depth):
        """
        This returns true if this variable occurrence is bound by varname.
        Uses DeBruijn indexing.
        @param varname: the  variable name
        @param depth below a quantifier, used for recursive calls
        @return a boolean
        """
        return varname == self.varname and self.db_index == depth

    def is_closed(self,depth):
        """
        Tests if a formula is closed by existential quantifiers only.
        Tests if this var is bound by a quantifier in a formula
        @param depth from the top quantifier
        @return true if this var is bound in the formula, false otherwise
        """
        return self.db_index <= depth
                    
    def value(self):
        """
        This does in-place normalisation of the body of this abstraction
        @return self
        """
        return self

    def __str__(self):
        return "%s-%d"%(self.varname,self.db_index)

class LambdaAbstraction:
    
    def __init__(self,boundvar_name,boundvar_type,body):
        """
        That creates the Lambda Abstraction term \boundvar_name:boundvar_type (func_body)
        @param boundvar_name: the bounded variable name
        @param boundvar_type: the bounded variable type
        @param body: a lambda term
        """
        self.boundvar_name,self.boundvar_type = boundvar_name,boundvar_type
        self.body = body
        self.bind_var(self.boundvar_name,self.boundvar_type)
        
    def copy(self,db_update=0,depth=0):
        """
        Performs a deep copy of the term and returns it
        @param db_update: a number with which to update db_indexes
        @return a LambdaTerm
        """
        return LambdaAbstraction(self.boundvar_name,self.boundvar_type,self.body.copy(db_update,depth+1))
    
    def bind_var(self,varname,vartype,depth=0):
        """
        This captures variables inside the body and indexes them with
        DeBruijn indexes. Used only at init.
        @param varname: the name of the variable to bind
        @param vartype: the type of the variable to bind 
        @param depth below a quantifier, used for recursive calls
        """
        self.body.bind_var(varname,vartype,depth+1)

    def substitute(self,varname,replacement,depth=0):
        """
        This performs the substitution of a varname by a replacement term.
        Uses DeBruijn indexing.
        @param varname: the  variable name
        @param replacement: the replacement term
        @param depth below a quantifier, used for recursive calls
        """
        depth += 1
        if isinstance(self.body,LambdaVariable):
            if self.body.is_bound(varname,depth):
                self.body = replacement.copy(db_update=depth-1)
            elif self.body.db_index - depth > 0 : #if var is free...
                self.body.db_index -= 1
        else:
            self.body.substitute(varname,replacement,depth)

    def is_closed(self,depth):
        """
        Tests if a formula is closed by existential quantifiers only.
        @param depth from the top quantifier
        @return true if this var is bound in the formula, false otherwise
        """
        return False
            
    def value(self):
        """
        This does in-place normalisation of the body of this abstraction.
        @return a lambda term
        """
        self.body = self.body.value()
        return self

    def __str__(self):
        return '(lambda (%s:%s) %s)'%(self.boundvar_name,self.boundvar_type,str(self.body))

class LambdaApplication:
    
    def __init__(self,termA,termB):
        """
        That's the Lambda Application of the form (A B)
        @param termA: the left term
        @param termB: the right term
        """
        self.termA,self.termB = termA,termB
                
    def copy(self,db_update=0,depth=0):
        """
        Performs a deep copy of the term and returns it
        @param db_update: a number with which to update db_indexes
        @return a LambdaTerm
        """
        return LambdaApplication(self.termA.copy(db_update,depth),self.termB.copy(db_update,depth))
        
    def bind_var(self,varname,vartype,depth=0):
        """
        This captures variables inside the body and indexes them with
        DeBruijn indexes. Used only at init.
        @param varname: the name of the variable to bind
        @param vartype: the type of the variable to bind 
        @param depth below a quantifier, used for recursive calls
        """
        self.termA.bind_var(varname,vartype,depth)
        self.termB.bind_var(varname,vartype,depth)
        
    def substitute(self,varname,replacement,depth=0):
        """
        This performs the substitution of a varname by a replacement term.
        Uses DeBruijn indexing.
        @param varname: the  variable name
        @param replacement: the replacement term
        @param depth below a quantifier, used for recursive calls
        """
        if isinstance(self.termA,LambdaVariable):
            if self.termA.is_bound(varname,depth):
                self.termA = replacement.copy(db_update=depth-1)
            elif self.termA.db_index - depth > 0 : #var is free ?
                self.termA.db_index -= 1
        else:
            self.termA.substitute(varname,replacement,depth)

        if isinstance(self.termB,LambdaVariable):
            if self.termB.is_bound(varname,depth):
                self.termB = replacement.copy(db_update=depth-1)
            elif self.termB.db_index - depth > 0 : #var is free ?:
                self.termB.db_index -= 1
        else:
            self.termB.substitute(varname,replacement,depth)

    def is_closed(self,depth):
        """
        Tests if a formula is closed by existential quantifiers only.
        @param depth from the top quantifier
        @return true if this var is bound in the formula, false otherwise
        """
        return self.termA.is_closed(depth) and self.termB.is_closed(depth)
                
    def value(self):
        """
        This does a call by value beta reduction.
        Inplace operation.
        @return a normalized lambda term (a value) if it exists
        """
        self.termA = self.termA.value()
        
        #generic (normal) case
        if isinstance(self.termA,LambdaAbstraction):
            self.termB = self.termB.value()
            self.termA.substitute(self.termA.boundvar_name,self.termB)
            return self.termA.body.value()
        
        #external func case
        elif isinstance(self.termA,ConstantFunction):
            self.termB = self.termB.value()
            self.termA.substitute(replacement=self.termB)
            return self.termA.value()
        
        #otherwise (failed application)...
        self.termB = self.termB.value()   
        return self
    
    def sparql_value(self,answer_vars,varbindings):
        return self.termA.sparql_value(answer_vars,varbindings)
    
    def __str__(self):
        return "(%s %s)"%(str(self.termA),str(self.termB))


#EXTENSIONS
class ExistentialQuantifier(object):
    
    def __init__(self,boundvar_name,boundvar_type,body):
        """
        That creates an Existential quantifier term (exists (boundvar_name:boundvar_type) (func_body) )
        @param boundvar_name: the bounded variable name
        @param boundvar_type: the bounded variable type
        @param body: a lambda term
        or not.
        """
        self.boundvar_name,self.boundvar_type = boundvar_name,boundvar_type
        self.body = body
        self.bind_var(self.boundvar_name,self.boundvar_type)

    def copy(self,db_update=0,depth=0):
        """
        Performs a deep copy of the term and returns it
        @param db_update: a number with which to update db_indexes
        @return a ExistentialQuantifier instance
        """
        return ExistentialQuantifier(self.boundvar_name,self.boundvar_type,self.body.copy(db_update,depth+1))

    def bind_var(self,varname,vartype,depth=0):
        """
        This captures variables inside the body and indexes them with
        DeBruijn indexes. Used only at init.
        @param varname: the name of the variable to bind
        @param vartype: the type of the variable to bind 
        @param depth below a quantifier, used for recursive calls
        """
        self.body.bind_var(varname,vartype,depth+1)

    def substitute(self,varname,replacement,depth=0):
        """
        This performs the substitution of a varname by a replacement term.
        Uses DeBruijn indexing.
        @param varname: the  variable name
        @param replacement: the replacement term
        @param depth below a quantifier, used for recursive calls
        """
        depth += 1
        if isinstance(self.body,LambdaVariable):
            if self.body.is_bound(varname,depth):
                self.body = replacement.copy(db_update=depth-1)
            elif self.body.db_index - depth > 0 : #if var is free...
                self.body.db_index -= 1
        else:
            self.body.substitute(varname,replacement,depth)

    def ret_value(self):
        """
        This evaluates the whole subformula behind this node against the database
        and returns a boolean (true or false) if there exists an assignment of the variables satisfied by the model.

        In case the subformula has not type 't' this function will fail.
        In this case, this prints an error message and returns False. 
        """
        raise NotImplementedError()
        #that's where you put the semantics of the existential quantif : find var assignment if it exists
        
    def value(self):
        """
        This does in-place normalisation of the body of this quantifier.
        @return a lambda term
        """
        self.body = self.body.value()
        return self

    def is_closed(self,depth=0):
        """
        @param : a dict of bound varnames with their depth
        Returns True if the expression contains variables bound only by quantifiers (no free variables and no vars bound by lambda terms
        """
        #tests if all vars occurrences dbindexes in subformulas are smaller then their depth 
        return self.body.is_closed(depth=depth+1)
        
    def __str__(self):
        
        if self.is_closed():
            print('quantifier closed')
            return str(self.ret_value())
        else:
            print('quantifier not closed')
            return '(exists (%s:%s) %s)'%(self.boundvar_name,self.boundvar_type,str(self.body))


class ConstantFunction(object):
    """
    It allows to encode external functions and constants typically involving I/O and python processing or data types
    
    This class is meant to be subclassed, for expressing specialized functions, the ret_value method has to be overloaded.

    It emulates the behaviour of a lambda abstraction for several arguments.
    The return value is constant and may be accessed as soon as all the params of the function are bound to constant values

    A constant is a constant function without arguments.
    
    To instanciate a constant, use the make_constant wrapper.
    To instanciate a function, use the make function wrapper.
    """
    def __init__(self,name=None,const_value=None,argtypes=[],ret_type=TypeSystem.FAILURE):
        """
        The constructor takes the signature of the function as parameters
        @param name: the name of the function 
        @param value: the value of the constant
        @param argtypes: a list of atomic types for the func params
        @param ret_type: the atomic type of the returned value or the type of the constant value
        """
        self.fun_name    = name
        self.ttype       = tuple(argtypes)+(ret_type,)
        self.val         = const_value

        self.nargs = len(argtypes)
        self.args_values = [LambdaVariable("__x__",ttype=argtypes[idx],db_index=self.nargs-idx) for idx in range(self.nargs)]
            
    @staticmethod
    def make_constant(const_value,const_type):
        """
        Wrapper method for allocating a constant
        @param value: the constant value
        @param const_type: the constant type
        @return a ConstantFunction object
        """
        return ConstantFunction(const_value=const_value,ret_type=const_type)

    @staticmethod
    def make_function(name,argtypes,ret_type):
        """
        Wrapper method for allocating a function returning an atomic value
        @param name: the name of the function 
        @param argtypes: a list of atomic types for the func params
        @param ret_type: the atomic type of the returned value or the type of the constant value
        """
        return ConstantFunction(name=name,argtypes = argtypes,ret_type=ret_type)
    
    def copy(self,db_update=0,depth=0):
        """
        This copy method can be inherited by subclasses
        """
        cpy = copy.deepcopy(self) #allows inheritance by subclasses ; shallow copy instead ?
        for idx in range(len(cpy.args_values)):
            term = cpy.args_values[idx]
            cpy.args_values[idx] = term.copy(db_update,depth+self.nargs)
        return cpy
        
    def bind_var(self,varname,vartype,depth=0):
        """
        This captures variables inside the body and indexes them with
        DeBruijn indexes. Used only at init.
        @param varname: the name of the variable to bind
        @param vartype: the type of the variable to bind 
        @param depth below a quantifier, used for recursive calls
        """
        pass
        #raise NotImplementedError()    
        #There is no way an external binder can bind an inner variable at init.
        #(but later on it becomes possible)

    def is_closed(self,depth):
        """
        @param : a dict of bound varnames with their depth
        Returns True if the expression contains variables bound only by quantifiers (no free variables and no vars bound by lambda terms)
        """
        return self.nargs == 0 and all([v.is_closed(depth) for v in self.args_values])
        
    def substitute(self,varname=None,replacement=None,depth=0):
        """
        This performs the substitution of a varname by a replacement term.
        Uses DeBruijn indexing.
        @param varname: the  variable name
        @param replacement: the replacement term
        @param depth below a quantifier, used for recursive calls
        """
        #testA : (lambda (x:num y:num) (+ (+ x 3) (+ y 3)))
        #testB : (lambda (P:e=>t Q:e=>t) (exists (x:e) (and (P x) (Q x))))
        #testC : ((lambda (P:e=>t) (exists (x:e) (P x))) Q42)
        
        if depth < self.nargs:     # we are attempting a local substitution (we remove a local lambda binder)
            if varname == None:                
                varname = '__x__'
            depth += self.nargs
            for idx in range(len(self.args_values)):
                term = self.args_values[idx]
                if isinstance(term,LambdaVariable):
                    if term.is_bound(varname,depth):
                        self.args_values[idx] = replacement.copy(db_update=depth-1)
                        self.nargs -= 1
                    elif term.db_index - depth > 0:        #var is free
                        term.db_index -= 1
                else:
                    term.substitute(varname,replacement,depth)  #todo : check this one                            
        else:                          # we are performing a non-local substitution (we remove an outer lambda binder)
            depth += self.nargs
            for idx in range(len(self.args_values)):
                term = self.args_values[idx]
                if isinstance(term,LambdaVariable):
                    if term.is_bound(varname,depth):
                        self.args_values[idx] = replacement.copy(db_update=depth-1)
                    elif term.db_index - depth > 0:   #var is free
                        term.db_index -= 1
                else:
                    term.substitute(varname,replacement,depth)  #todo : check this one  

                            
    def ret_value(self):
        """
        This method computes a value (denotation) externally and returns it
        This is the interface towards the outer world.
        The only method that needs to be subclassed
        @return a value with python type matching the ret_type of the function      
        """
        return self.val

    def value(self):
        """
        This does a call by value beta reduction.
        @return a ConstantFunction object
        """
        for idx in range(len(self.args_values)):
            self.args_values[idx] = self.args_values[idx].value()
        return self

    def is_constant(self):
        """
        if true means that we can get the denotation (= call ret_value)
        """
        return all([isinstance(val,ConstantFunction) and val.is_constant() for val in self.args_values])
     
    def __str__(self):
        if self.is_constant():
            return str(self.ret_value()) 
        else:
            def pprint_arg(term):
                if isinstance(term,ConstantFunction) and term.is_constant():
                    return str(term.ret_value())
                elif isinstance(term,LambdaVariable):
                    return str(term)
                else:
                    return str(term)#'?'
                
            return '%s(%s)'%(self.fun_name,','.join([pprint_arg(val) for val in self.args_values]))


class SuperlativeCombinator(object):
    """
    This class codes an argmax/argmin style combinator that simulates
    the behaviour of a term of the form :
    (lambda (Q:e=>t P:e=>num=>t)  (exists (x:e) (Q x) and exists (v:num v':num) (P x v) and  (forall (y:e) (P y v') -> (v > v')))
    This roughly compares to the behaviour of the constant function except that it takes higher order arguments
    Q is a unary predicate of type e=>t
    P is binary predicate whose y value is numeric or a date
    (num|date)
    @TODO... 
    """
    def __init__(self):
        self.ttype        = ((TypeSystem.DB_ENTITY,TypeSystem.BOOLEAN),(TypeSystem.DB_ENTITY,TypeSystem.DB_ENTITY,TypeSystem.BOOLEAN),TypeSystem.BOOLEAN)
        self.nargs        = 2
        # Q variable
        self.entity_var   = LambdaVariable("__Q__",ttype=(TypeSystem.DB_ENTITY,TypeSystem.BOOLEAN),db_index=2)
        # P variable ANY TOO LAZY : accepts comparisons of strings too ! but works...
        self.quantity_var = LambdaVariable("__P__",ttype=((TypeSystem.DB_ENTITY,TypeSystem.ANY),TypeSystem.BOOLEAN),db_index=1)
        self.xarg_var     = LambdaVariable("__x__",ttype=(TypeSystem.DB_ENTITY),db_index=2)
        self.varg_var     = LambdaVariable("__v__",ttype=(TypeSystem.ANY),db_index=2)
        
    def copy(self,db_update=0,depth=0):
        """
        This copy method can be inherited by subclasses
        """
        #TODO !
        cpy = copy.deepcopy(self) #allows inheritance by subclasses ; shallow copy instead ?
        for idx in range(len(cpy.args_values)):
            term = cpy.args_values[idx]
            cpy.args_values[idx] = term.copy(db_update,depth+self.nargs)
        return cpy

    
    def bind_var(self,varname,vartype,depth=0):
        """
        This captures variables inside the body and indexes them with
        DeBruijn indexes. Used only at init.
        @param varname: the name of the variable to bind
        @param vartype: the type of the variable to bind 
        @param depth below a quantifier, used for recursive calls
        """
        pass
        #This case never happens (here for interface)

    def ret_value(self):
        """
        This method computes a value (denotation) externally and returns it
        This is the interface towards the outer world.
        The only method that needs to be subclassed
        @return a value with python type matching the ret_type of the function      
        """
        #valuation check : arg0 must be an externally bound variable and one must find a property constant in arg1
        return self.val

    def value(self):
        """
        This does a call by value beta reduction.
        @return a Superlative Function object
        """
        for idx in range(len(self.args_values)):
            self.args_values[idx] = self.args_values[idx].value()
        return self

    def is_evaluable(self):
        """
        Returns true when this quantifier can return a proper truth
        value. Here we allow evaluation as soon as all the pseudo-binders are gone.
        """
        return self.nargs == 0
    
    def sparql_value(self,answer_vars,var_bindings):
        """
        This generates a SPARQL query for the predicate
        @param answer_vars : variables whose bindings are answers to the question 
        @param var_bindings: a dict sparql_varname: depth
        @return: a string part of the query

        USE SPARQL subqueries
        @see https://www.w3.org/TR/2013/REC-sparql11-query-20130321/#subqueries

        Example ARGMAX for Mt Everest : 
        (lambda (Q:e=>t P:e=>num=>t)  (exists (x:e) (Q x) and exists (v:num v':num) (P x v) and (forall (y:e) (P y v' ) -> (v > v') ))

        The translation will not use p and q :
        SELECT ?x WHERE{           # GENERIC QUERY
          {                        # ARGMAX SUBQUERY
             SELECT ?x WHERE {
                ?x wdt:P31 wd:Q8502 .   # Restr    : Mountain(x)   #translation of arg (Q x) of the lambda term.
                ?x wdt:P2660 ?v .       # Altitude : Altitude(x,v) #translation of arg (P x v) of the lambda term.
          }ORDER BY DESC(?v)
           LIMIT 1                      #Can generalize to K-Argmax and to offsets here.
         } #END SUBQUERY
          
        }
        Conclusion: the class emulates the process by:
        introducing Q P lambda vars as args, an x var that gets bound by Q and P and a dummy ?y var that gets bound by P.
        """
        pass
    
        return """
        OPTIONAL {
             %s %s %s  #predicate stuff
             FILTER ( < ) .
        } .
        FILTER ( ! %s ) .
        """%(...)
        
    def __str__(self):
        if self.is_evaluable():
            return str(self.ret_value())
        else:
            return '%s(%s)'%('argmax',','.join([str(val) for val in self.args_values]))

        
#Arithmetic functions
class ExtAddition(ConstantFunction):
    """
    Implements arithmetic addition
    """
    def __init__(self):
        super().__init__(name="+",argtypes=(TypeSystem.NUMERIC,TypeSystem.NUMERIC),ret_type=TypeSystem.NUMERIC)

    def ret_value(self):
        res = float(self.args_values[0].ret_value()) + float(self.args_values[1].ret_value())
        return res
        
class ExtSubstraction(ConstantFunction):
    """
    Implements arithmetic substraction
    """
    def __init__(self):
        super().__init__(name="-",argtypes=(TypeSystem.NUMERIC,TypeSystem.NUMERIC),ret_type=TypeSystem.NUMERIC)
        
    def ret_value(self):
        res = float(self.args_values[0].ret_value()) - float(self.args_values[1].ret_value()) 
        return res
        
class ExtMultiplication(ConstantFunction):
    """
    Implements arithmetic multiplication
    """
    def __init__(self):
        super().__init__(name="*",argtypes=(TypeSystem.NUMERIC,TypeSystem.NUMERIC),ret_type=TypeSystem.NUMERIC)

    def ret_value(self):
        res = float(self.args_values[0].ret_value()) * float(self.args_values[1].ret_value()) 
        return res

class ExtDivision(ConstantFunction):
    """
    Implements arithmetic division
    """
    def __init__(self):
        super().__init__(name="/",argtypes=(TypeSystem.NUMERIC,TypeSystem.NUMERIC),ret_type=TypeSystem.NUMERIC)
        
    def ret_value(self):
        res = float(self.args_values[0].ret_value()) / float(self.args_values[1].ret_value()) 
        return res

#Boolean functions
class ExtAnd(ConstantFunction):
    """
    Implements logical and
    """
    def __init__(self):
        super().__init__(name="and",argtypes=(TypeSystem.BOOLEAN,TypeSystem.BOOLEAN),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        res = self.args_values[0].ret_value() and self.args_values[1].ret_value()
        return res

class ExtOr(ConstantFunction):
    """
    Implements logical or
    """
    def __init__(self):
        super().__init__(name="or",argtypes=(TypeSystem.BOOLEAN,TypeSystem.BOOLEAN),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        res = self.args_values[0].ret_value() or self.args_values[1].ret_value()
        return res

class ExtNot(ConstantFunction):
    """
    Implements logical not
    """
    def __init__(self):
        super().__init__(name="not",argtypes=(TypeSystem.BOOLEAN,),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        return not self.args_values[0].ret_value()
    
#comparisons
#we use the ANY type. For most of the atomic types these comparisons make sense.
class ExtEqual(ConstantFunction):
    """
    Implements == 
    """
    def __init__(self):
        super().__init__(name="==",argtypes=(TypeSystem.ANY,TypeSystem.ANY),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        print(type(self.args_values[0].ret_value()),type(self.args_values[1].ret_value()))
        res = self.args_values[0].ret_value() == self.args_values[1].ret_value()
        return res

class ExtNotEqual(ConstantFunction):
    """
    Implements != 
    """
    def __init__(self):
        super().__init__(name="!=",argtypes=(TypeSystem.ANY,TypeSystem.ANY),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        res = self.args_values[0].ret_value() != self.args_values[1].ret_value()
        return res

class ExtLess(ConstantFunction):
    """
    Implements < 
    """
    def __init__(self):
        super().__init__(name="<",argtypes=(TypeSystem.ANY,TypeSystem.ANY),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        res = self.args_values[0].ret_value() < self.args_values[1].ret_value()
        return res

class ExtLessEq(ConstantFunction):
    """
    Implements <= 
    """
    def __init__(self):
        super().__init__(name="<=",argtypes=(TypeSystem.ANY,TypeSystem.ANY),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        res = self.args_values[0].ret_value() <= self.args_values[1].ret_value()
        return res

class ExtGreater(ConstantFunction):
    """
    Implements > 
    """
    def __init__(self):
        super().__init__(name=">",argtypes=(TypeSystem.ANY,TypeSystem.ANY),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        res = self.args_values[0].ret_value() > self.args_values[1].ret_value()
        return res

    
class ExtGreaterEq(ConstantFunction):
    """
    Implements >=
    """
    def __init__(self):
        super().__init__(name=">=",argtypes=(TypeSystem.ANY,TypeSystem.ANY),ret_type=TypeSystem.BOOLEAN)

    def ret_value(self):
        res = self.args_values[0].ret_value() >= self.args_values[1].ret_value()
        return res
    
#String functions
class ExtCarS(ConstantFunction):
    pass

class ExtConsS(ConstantFunction):
    pass

class ExtCdrS(ConstantFunction):
    pass


    
