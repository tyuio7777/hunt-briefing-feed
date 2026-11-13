"""Read the literal-only data subset emitted by Svelte. Never execute source JS."""
import json, re

class LiteralError(ValueError): pass

class Reader:
    def __init__(self, text, pos=0, refs=None):
        self.text, self.pos, self.refs = text, pos, refs or {}
    def ws(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace(): self.pos += 1
    def take(self, token):
        self.ws()
        if not self.text.startswith(token, self.pos):
            raise LiteralError(f'Expected {token!r} at {self.pos}: {self.text[self.pos:self.pos+60]}')
        self.pos += len(token)
    def ident(self):
        self.ws(); m = re.match(r'[A-Za-z_$][\w$]*', self.text[self.pos:])
        if not m: raise LiteralError('Expected identifier')
        self.pos += len(m[0]); return m[0]
    def string(self):
        quote = self.text[self.pos]; self.pos += 1; out=[]
        escapes={'n':'\n','r':'\r','t':'\t','b':'\b','f':'\f','v':'\v','0':'\0'}
        while self.pos < len(self.text):
            c=self.text[self.pos]; self.pos+=1
            if c == quote: return ''.join(out)
            if quote=='`' and c=='$' and self.text[self.pos:self.pos+1]=='{':
                raise LiteralError('Template expressions are forbidden')
            if c=='\\':
                c=self.text[self.pos];self.pos+=1
                if c in ('u','x'):
                    n=4 if c=='u' else 2; out.append(chr(int(self.text[self.pos:self.pos+n],16)));self.pos+=n
                else: out.append(escapes.get(c,c))
            else: out.append(c)
        raise LiteralError('Unterminated string')
    def value(self, depth=0):
        if depth > 100: raise LiteralError('Data nesting limit')
        self.ws(); c = self.text[self.pos]
        if c in ('"', "'", '`'): return self.string()
        if c == '!' and self.text[self.pos+1:self.pos+2] in ('0','1'):
            self.pos += 2; return self.text[self.pos-1]=='0'
        if c in '{[':
            self.pos += 1; out = {} if c == '{' else []; end = '}' if c == '{' else ']'
            self.ws()
            while self.text[self.pos] != end:
                if c == '{':
                    key = self.string() if self.text[self.pos] in ('"', "'", '`') else self.ident()
                    if key in out: raise LiteralError('Duplicate property')
                    self.take(':'); out[key] = self.value(depth+1)
                else: out.append(self.value(depth+1))
                self.ws()
                if self.text[self.pos] == end: break
                self.take(','); self.ws()
            self.take(end); return out
        if c == '(':
            self.take('('); v = self.value(depth+1); self.take(')'); return v
        m = re.match(r'-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', self.text[self.pos:])
        if m:
            self.pos += len(m[0]); return float(m[0]) if any(x in m[0] for x in '.eE') else int(m[0])
        name = self.ident()
        if name in ('true','false','null'): return {'true':True,'false':False,'null':None}[name]
        if name == 'void': self.take('0'); return None
        if name == 'function':
            self.take('('); names=[]; self.ws()
            while self.text[self.pos] != ')':
                names.append(self.ident()); self.ws()
                if self.text[self.pos] != ')': self.take(',')
            self.take(')'); self.take('{')
            previous = self.refs; self.refs = {n: {'$literalRef':n} for n in names}
            assignments=[]
            self.ws()
            while not self.text.startswith('return',self.pos):
                name=self.ident()
                if name not in names: raise LiteralError('Unknown data binding')
                self.take('.'); key=self.ident(); self.take('=')
                assignments.append((name,key,self.value(depth+1))); self.take(';'); self.ws()
            self.take('return')
            body = self.value(depth+1); self.refs = previous
            self.take('}'); self.take('('); args=[]; self.ws()
            while self.text[self.pos] != ')':
                args.append(self.value(depth+1)); self.ws()
                if self.text[self.pos] != ')': self.take(',')
            self.take(')')
            if len(names) != len(args): raise LiteralError('Argument count mismatch')
            refs = dict(zip(names,args))
            def resolve(v):
                if isinstance(v,dict):
                    if set(v)=={'$literalRef'}: return refs[v['$literalRef']]
                    return {k:resolve(x) for k,x in v.items()}
                if isinstance(v,list): return [resolve(x) for x in v]
                return v
            for name,key,value in assignments:
                if not isinstance(refs[name],dict): raise LiteralError('Expected literal record binding')
                refs[name][key]=resolve(value)
            return resolve(body)
        if name in self.refs: return self.refs[name]
        raise LiteralError('Unsupported expression: ' + name)

def hydration(document):
    marker = 'data: ['
    start = document.rfind(marker)
    if start < 0: raise LiteralError('No page data')
    reader = Reader(document, start + len('data: '))
    result = reader.value()
    if not isinstance(result,list): raise LiteralError('Expected page data array')
    return [x['data'] for x in result if isinstance(x,dict) and x.get('type')=='data']
