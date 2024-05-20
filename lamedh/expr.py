from copy import deepcopy

from lamedh.visitors import FreeVarVisitor, BoundVarVisitor, SubstituteVisitor, RedicesVisitor


class StopEvaluation(Exception):
    pass


class CantEvalException(Exception):
    pass


class CantReduceException(Exception):
    pass


class CantReduceToCanonicalException(Exception):
    pass


class Expr:

    @staticmethod
    def from_string(expr_str):
        # import here to avoid circular import error
        from lamedh.parsing.parsing import lambda_parser
        return lambda_parser.parse(expr_str)

    def clone(self):
        return deepcopy(self)

    def get_free_vars(self):
        return FreeVarVisitor().visit(self)

    def is_redex(self):
        return False

    def goto_root(self):
        node = self
        while node.parent:
            node = node.parent
        return node

    def get_redices(self):
        root = self.goto_root()
        return RedicesVisitor().visit(root)

    def is_normal(self):
        return len(self.get_redices()) == 0

    def is_canonical(self):
        root = self.goto_root()
        return isinstance(root, Lam)

    def reduce(self):
        raise CantReduceException()

    def goto_canonical(self, max_steps=10, verbose=False):
        root = self.goto_root().clone()
        step = 0
        while not root.is_canonical() and step < max_steps:
            redices = root.get_redices()
            if not redices:
                raise CantReduceToCanonicalException
            redex = redices[0]  # try to reduce outer most first
            root = redex.reduce().goto_root()
            step += 1
            if verbose:
                print(root)
        return root

    def goto_normal(self, max_steps=10, verbose=False):
        step = 0
        def show(expr):
            print('step', step, '->', expr, '    ', len(expr.get_redices()))
        root = self.goto_root().clone()
        if verbose:
            show(root)
        while not root.is_normal() and step < max_steps:
            redices = root.get_redices()
            if not redices:
                raise CantReduceToCanonicalException
            redex = redices[-1]  # try to reduce inner most first, always
            root = redex.reduce().goto_root()
            step += 1
            if verbose:
                show(root)
        return root


class Var(Expr):

    def __init__(self, name):
        self.parent = None
        self.var_name = name

    def __repr__(self):
        return self.var_name

    def rename(self, new_name):
        assert isinstance(new_name, str)
        self.var_name = new_name


class Lam(Expr):

    def __init__(self, name, body):
        self.parent = None
        assert isinstance(name, str)
        self.var_name = name
        assert isinstance(body, Expr)
        self.body = body
        self.body.parent = self

    def __repr__(self):
        return f'(λ{self.var_name}.{self.body})'

    def children(self):
        return [self.body]

    def replace_child(self, old, new):
        new.parent = self
        self.body = new

    def bound_var_occurrence(self):
        # Returns all occurrences of variables this lambda's is binding
        return BoundVarVisitor().visit(self, self.var_name)

    def rename(self, new_name):
        assert isinstance(new_name, str)
        for occ in self.bound_var_occurrence():
            occ.rename(new_name)
        self.var_name = new_name


class App(Expr):

    def __init__(self, operator, operand):
        self.parent = None
        assert isinstance(operator, Expr)
        assert isinstance(operand, Expr)
        self.operator = operator
        self.operand = operand
        operator.parent = self
        operand.parent = self

    def children(self):
        return [self.operator, self.operand]

    def __repr__(self):
        return f'({self.operator} {self.operand})'

    def is_redex(self):
        return isinstance(self.operator, Lam)

    def replace_child(self, old, new):
        new.parent = self
        if self.operator == old:
            self.operator = new
        if self.operand == old:
            self.operand = new

    def reduce(self):
        # Reducing redices WILL modify objects in-place.
        # If needed to preserve original structure, caller must make a copy
        # before calling reduce
        if not self.is_redex():
            raise CantReduceException()

        lam = self.operator
        arg = self.operand
        mapping = {lam.var_name: arg.clone()}
        substituted = SubstituteVisitor().visit(lam.body, mapping)

        if self.parent:
            self.parent.replace_child(self, substituted)
        substituted.parent = self.parent
        return substituted

