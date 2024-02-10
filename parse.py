from typing import List, Generator, Iterable
import re
from sys import stderr, stdout, exit, argv
import fileinput
from xml.dom import minidom
from xml.sax.saxutils import unescape


class ParseError(Exception):
    """
    Chyba při zpracovánání programu jazyka IPPcode24.
    """

    def __init__(self, message: str, code: int):
        self.exit_code = code
        super().__init__(message)


class SourceError(ParseError):
    """
    Chyba při kontrole lexikální nebo syntaktické správnosti jazyka IPPcode24.
    """

    def __init__(self, message: str):
        super().__init__('Lexikální nebo syntaktická chyba: ' + message, 23)


class Argument:
    """
    Argument instrukce jayzka IPPcode24.
    """

    def __init__(self, ipptype: str, text: str):
        self.ipptype = ipptype
        self.text = text

    def __str__(self):
        if self.ipptype in ('string', 'bool', 'int', 'nil'):
            return f'{self.ipptype}@{unescape(self.text)}'
        else:
            return self.text


class Instruction:
    """
    Instrukce jayzka IPPcode24.
    """

    def __init__(self, order: int, opcode: str, *args: Argument):
        self.order = order
        self.opcode = opcode
        self.args = args

        if len(args) > 3:
            raise RuntimeError('Počet argumentů musí být menší nebo roven 3')

    def __str__(self):
        result = self.opcode

        if self.args:
            result += ' ' + ' '.join(str(a) for a in self.args)

        return result

def remove_comment(line: str) -> str:
    """
    Odstraní z jednoho řádku komentář.
    Pokud řádek žádný komentář neobsahuje, vrátí nezměněný řetězec.
    """

    idx = line.find('#')

    if idx == -1:
        return line

    return line[:idx]


def parse_variable(variable_str: str) -> Argument:
    """
    Převede řetězec s proměnnou jazyka IPPcode24 na její vnitřní reprezentaci.
    Pokud není proměnná lexikálě správná, nastává chyba.
    """

    match = re.match('^(LF|TF|GF)@([a-zA-Z_$&%*!?][a-zA-Z0-9_$&%*!?]*)$', variable_str)

    if match is None:
        raise SourceError(f'Proměnná ve špatném formátu: "{variable_str}"')

    return Argument('var', variable_str)


def is_ippcode_integer(integer_str: str) -> bool:
    """
    Zkontroluje, jestli je obsah řetězce lexikálně správná celočíselná konstanta jazyka IPPcode24.
    """

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
    """
    Převede řetězec s konstantu jazyka IPPcode24 na její vnitřní reprezentaci,
    pokud není konstanta lexikálně správna, nastává chyba.
    """

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
    """
    Převede řetězec s návěstím na jeho vnitřní reprezentaci,
    pokud není návěstí lexikálně správné, nastává chyba.
    """

    if re.match(r'^([^ \t\r\n\x00-\x1F#\\]|\\[0-9]{3})+$', label_str) is None:
        raise SourceError(f'Návěstí ve špatném formátu: "{label_str}"')

    return Argument('lable', label_str)


def is_possibly_literal(literal_str: str) -> bool:
    """
    Zkontroluje, jestli obsah řetězce vypadá jako konstanta jazyka IPPcode24
    """

    return any(literal_str.startswith(t) for t in ['int', 'bool', 'string', 'nil'])


def is_possibly_variable(variable_str: str) -> bool:
    """
    Zkontroluje, jestli obsah řetězce vypadá jako proměnná jazyka IPPcode24
    """

    return any(variable_str.startswith(t) for t in ['TF', 'LF', 'GF'])


def parse_symbol(symbol_str: str) -> Argument:
    """
    Převede řetězec s proměnnou nebo konstantu na vnitřní reprezentaci,
    pokud obsah řetězce není lexikálně správný, nastává chyba.
    """

    if is_possibly_literal(symbol_str):
        return parse_literal(symbol_str)
    elif is_possibly_variable(symbol_str):
        return parse_variable(symbol_str)
    else:
        raise SourceError(f'Symbol ve špatném formátu: "{symbol_str}"')


def parse_type(ipptype_str: str) -> Argument:
    """
    Převede řetězec s datovým typem jazyka IPPcode24 na jeho vnitřní reprezentaci,
    pokud typ není lexikálně psrávný, nastává chyba.
    """

    if ipptype_str not in ('int', 'string', 'bool'):
        raise SourceError(f'neznámý typ: "{ipptype_str}"')

    return Argument('type', ipptype_str)


def tokenize_line(line: str) -> List[str]:
    """
    Odstraní komentář a rozdělí řádek na podřetězce tak, aby každý podřetězec obsahoval jeden token.
    U podřetězce s operačním kódem převede všechna malá písmena na velká.
    """

    parts = remove_comment(line).strip().split()

    if len(parts) > 0:
        parts[0] = parts[0].upper()

    return parts


def find_header(lines: List[str]) -> int:
    """
    Najde v posloupnosti řádků hlavičku programu IPPcode24 a vrátí index řádku s touto hlavičkou.
    Pokud halvička nebyla nalezena, vrací -1.
    """

    for line_idx, line in enumerate(lines):
        if re.match(r'^[^\S\r\n]*(\.IPPcode24)[^\S\r\n]*(#.*)?$', line):
            return line_idx
        elif not re.match(r'^[^\S\r\n]*(#.*)?$', line):
            return -1

    return -1


def parse_program(lines: List[str]) -> Generator[Instruction, None, None]:
    """
    Převede posloupnost řádků vstupního programu v jazyce IPPcode24 na vnitřní reprezentaci programu.
    """

    header_line_idx = find_header(lines)

    if header_line_idx == -1:
        stderr.writelines(lines)
        raise ParseError('Chybná nebo chybějící hlavička', 21)

    OPCODES = ('CREATEFRAME', 'PUSHFRAME', 'POPFRAME', 'RETURN', 'BREAK',
               'CALL', 'LABEL', 'JUMP', 'MOVE', 'INT2CHAR', 'STRLEN', 'TYPE',
               'MOVE', 'INT2CHAR', 'STRLEN', 'TYPE', 'ADD', 'SUB', 'MUL',
               'IMUL', 'DIV', 'IDIV', 'LT', 'GT', 'EQ', 'AND', 'OR', 'NOT',
               'CONCAT', 'GETCHAR', 'SETCHAR', 'STRI2INT', 'PUSHS', 'WRITE',
               'DPRINT', 'EXIT', 'POPS', 'DEFVAR', 'READ', 'JUMPIFEQ', 'JUMPIFNEQ')

    order = 1
    for line in lines[header_line_idx+1:]:
        tokens = tokenize_line(line)

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
                yield Instruction(order, opcode, parse_variable(var))

            case 'READ', var, ipptype:
                yield Instruction(order, 'READ', parse_variable(var), parse_type(ipptype))

            case ('JUMPIFEQ' | 'JUMPIFNEQ') as opcode, label, symb1, symb2:
                yield Instruction(order, opcode, parse_label(label), parse_symbol(symb1), parse_symbol(symb2))

            case []:
                continue

            case _:
                if tokens[0] not in OPCODES:
                    raise ParseError(f'Neznámý nebo chybný operační kód: "{tokens[0]}"', 22)
                else:
                    raise SourceError(f'Špatný počet argumentů: "{tokens}"')

        order += 1


def instructions_to_xml(instructions: Iterable[Instruction]) -> minidom.Document:
    """
    Převede vnitřní reprezantaci instrukcí na XML dokument.
    """

    document = minidom.Document()

    root = document.createElement('program')
    root.setAttribute('language', 'IPPcode24')
    document.appendChild(root)

    for instruction in instructions:
        ins_elem = document.createElement('instruction')
        ins_elem.setAttribute('order', str(instruction.order))
        ins_elem.setAttribute('opcode', instruction.opcode)

        for arg_idx, arg in enumerate(instruction.args, 1):
            arg_elem = document.createElement(f'arg{arg_idx}')
            arg_elem.setAttribute('type', arg.ipptype)
            arg_text_node = document.createTextNode(arg.text)
            arg_elem.appendChild(arg_text_node)
            ins_elem.appendChild(arg_elem)

        root.appendChild(ins_elem)

    return document


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
        document.writexml(stdout, addindent='    ', newl='\n', encoding='utf-8')
    except Exception as err:
        raise ParseError(str(err), 12)


if __name__ == '__main__':
    try:
        main()
    except ParseError as err:
        print(err, file=stderr)
        exit(err.exit_code)
    except Exception as err:
        print('Internal error:', err, file=stderr)
        exit(99)
    else:
        exit(0)
