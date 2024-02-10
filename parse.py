from typing import List, Generator, Iterable
import re
from sys import stderr, stdout, exit, argv
import fileinput
from xml.dom import minidom
# from xml.sax.saxutils import escape


class ParseError(Exception):
    def __init__(self, message: str, code: int):
        self.code = code
        super().__init__(message)


class SourceError(ParseError):
    def __init__(self, message: str):
        super().__init__('Lexikální nebo syntaktická chyba: ' + message, 23)


class Argument:
    """
    comment
    """
    def __init__(self, ipptype: str, text: str):
        self.ipptype = ipptype
        self.text = text


class Instruction:
    """
    introduction
    """
    def __init__(self, order: int, opcode: str, *args: Argument):
        self.order = order
        self.opcode = opcode
        self.args = args

        if len(args) > 3:
            raise RuntimeError('Počet argumentů musí být menší nebo roven 3')


def remove_comment(line: str) -> str:
    """
    some comment removal
    """
    idx = line.find('#')

    if idx == -1:
        return line

    return line[:idx]


def parse_variable(variable_str: str) -> Argument:
    match = re.match('^(LF|TF|GF)@([a-zA-Z_$&%*!?][a-zA-Z0-9_$&%*!?]*)$', variable_str)

    if match is None:
        raise SourceError(f'Proměnná ve špatném formátu: "{variable_str}"')

    return Argument('var', variable_str)


def is_ippcode_integer(integer_str: str) -> bool:
    try:
        if '0x' in integer_str.lower():
            int(integer_str, 16)
        elif '0o' in integer_str.lower():
            int(integer_str, 8)
        else:
            int(integer_str, 10)

        return True
    except:
        return False


def parse_literal(literal_str: str) -> Argument:
    match = re.match('^(int|bool|string|nil)@(.*)$', literal_str)

    if match is None or len(match.groups()) != 2:
        raise SourceError(f'Konstanta ve špatném formátu: "{literal_str}"')

    typestr, value = match.groups()

    if typestr == 'int' and not is_ippcode_integer(value): # and re.match('^(+|-)?[0-9]+$', value) is None:
        raise SourceError(f'Celočíselná konstanta ve špatném formátu: "{literal_str}"')
    elif typestr == 'bool' and value not in ('true', 'false'):
        raise SourceError(f'Booleanská konstanta ve špatném formátu: "{literal_str}"')
    elif typestr == 'string' and re.match(r'^([^ \t\r\n\x00-\x1F#\\]|\\[0-9]{3})*$', value) is None:
        raise SourceError(f'Řetězcová konstanta ve špatném formátu: "{literal_str}"')
    elif typestr == 'nil' and value != 'nil':
        raise SourceError(f'Nil konstanta ve špatném formátu: "{literal_str}"')

    return Argument(typestr, value)


def parse_label(label_str: str) -> Argument:
    if re.match(r'^([^ \t\r\n\x00-\x1F#\\]|\\[0-9]{3})+$', label_str) is None:
        raise SourceError(f'Návěstí ve špatném formátu: "{label_str}"')

    return Argument('lable', label_str)


def is_possibly_literal(literal_str: str) -> bool:
    return any(literal_str.startswith(t) for t in ['int', 'bool', 'string', 'nil'])


def is_possibly_variable(variable_str: str) -> bool:
    return any(variable_str.startswith(t) for t in ['TF', 'LF', 'GF'])


def parse_symbol(symbol_str: str) -> Argument:
    if is_possibly_literal(symbol_str):
        return parse_literal(symbol_str)
    elif is_possibly_variable(symbol_str):
        return parse_variable(symbol_str)
    else:
        raise SourceError(f'Symbol ve špatném formátu: "{symbol_str}"')


def parse_type(ipptype_str: str) -> Argument:
    if ipptype_str not in ('int', 'string', 'bool'):
        raise SourceError(f'neznámý typ: "{ipptype_str}"')

    return Argument(ipptype_str, ipptype_str)


def tokenize_line(line: str) -> List[str]:
    result = remove_comment(line).strip()
    result = result.split()

    if len(result) > 0:
        result[0] = result[0].upper()

    return result


def parse_program(lines: List[str]) -> Generator[Instruction, None, None]:
    if not lines or lines[0] != '.IPPcode24\n':
        raise ParseError('Chybná nebo chybějící hlavička', 21)

    OPCODES = ('CREATEFRAME', 'PUSHFRAME', 'POPFRAME', 'RETURN', 'BREAK',
               'CALL', 'LABEL', 'JUMP', 'MOVE', 'INT2CHAR', 'STRLEN', 'TYPE',
               'MOVE', 'INT2CHAR', 'STRLEN', 'TYPE', 'ADD', 'SUB', 'MUL',
               'IMUL', 'DIV', 'IDIV', 'LT', 'GT', 'EQ', 'AND', 'OR', 'NOT',
               'CONCAT', 'GETCHAR', 'SETCHAR', 'STRI2INT', 'PUSHS', 'WRITE',
               'DPRINT', 'EXIT', 'POPS', 'DEFVAR', 'READ', 'JUMPIFEQ', 'JUMPIFNEQ')

    order = 1
    for line in lines[1:]:
        tokens = tokenize_line(line)

        if tokens and tokens[0] not in OPCODES:
            raise ParseError(f'Neznámý nebo chybný operační kód: "{tokens[0]}"', 22)

        match tokens:
            case ('CREATEFRAME' | 'PUSHFRAME' | 'POPFRAME' | 'RETURN' | 'BREAK') as opcode,:
                yield Instruction(order, opcode)

            case ('CALL' | 'LABEL' | 'JUMP') as opcode, label:
                yield Instruction(order, opcode, parse_label(label))

            case ('MOVE' | 'INT2CHAR' | 'STRLEN' | 'TYPE') as opcode, var, symb:
                yield Instruction(order, opcode, parse_variable(var), parse_symbol(symb))

            case ('ADD' | 'SUB' | 'MUL' | 'IMUL' | 'DIV' | 'IDIV' | 'LT' | 'GT' | 'EQ' |
                  'AND' | 'OR' | 'NOT' | 'CONCAT' | 'GETCHAR' | 'SETCHAR' | 'STRI2INT') as opcode, var, symb1, symb2:
                yield Instruction(order, opcode, parse_variable(var), parse_symbol(symb1), parse_symbol(symb2))

            case ('PUSHS' | 'WRITE' | 'DPRINT' | 'EXIT') as opcode, symb:
                yield Instruction(order, opcode, parse_symbol(symb))

            case ('POPS' | 'DEFVAR') as opcode, var:
                yield Instruction(order, 'POPS', parse_variable(var))

            case 'READ', var, ipptype:
                yield Instruction(order, 'READ', parse_type(ipptype))

            case ('JUMPIFEQ' | 'JUMPIFNEQ') as opcode, label, symb1, symb2:
                yield Instruction(order, opcode, parse_label(label), parse_symbol(symb1), parse_symbol(symb2))

            case []:
                continue

            case _:
                raise SourceError(f'Špatný počet argumentů: "{tokens}"')

        order += 1


def instructions_to_xml(instructions: Iterable[Instruction]) -> minidom.Document:
    doc = minidom.Document()

    root = doc.createElement('program')
    root.setAttribute('language', 'IPPcode24')
    doc.appendChild(root)

    for instruction in instructions:
        elem = doc.createElement('instruction')
        elem.setAttribute('order', str(instruction.order))
        elem.setAttribute('opcode', instruction.opcode)

        for arg_idx, arg in enumerate(instruction.args, 1):
            arg_elem = doc.createElement(f'arg{arg_idx}')
            arg_elem.setAttribute('type', arg.ipptype)
            text_node = doc.createTextNode(arg.text)
            arg_elem.appendChild(text_node)
            elem.appendChild(arg_elem)

        root.appendChild(elem)

    return doc


def main():
    HELP = 'Načte ze standardního vstupu zdrojový kód v IPPcode24, ' \
           'zkontroluje lexikální a sytaktickou správnost kódu a ' \
           'vypíše na standardní výstup XML reprezentaci programu.'

    if len(argv) == 2 and argv[1] == '--help':
        print(HELP)
        return
    elif len(argv) > 2:
        raise ParseError('Zakázaná kombinace parametrů', 10)

    try:
        lines = fileinput.input(encoding='utf-8')
    except Exception as err:
        raise ParseError(str(err), 11)

    instructions = parse_program(list(lines))
    document = instructions_to_xml(instructions)

    try:
        document.writexml(stdout, indent='  ', addindent='  ', newl='\n', encoding='utf-8')
    except Exception as err:
        raise ParseError(str(err), 12)


try:
    main()
except ParseError as err:
    print(err, file=stderr)
    exit(err.code)
except Exception as err:
    print('Internal error:', err, file=stderr)
    exit(99)
else:
    exit(0)
