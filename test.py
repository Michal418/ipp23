import json
from pathlib import Path
import subprocess
from typing import List, Generator


GREEN = '\033[92m' #]
RED = '\033[91m' #]
BLUE = '\033[94m' #]
MAGENTA = '\033[95m' #]
CYAN = '\033[96m' #]
RESET = '\033[0m' #]


def color(s: str, color: str) -> str:
    return f'{color}{s}{RESET}'


def blue(s: str) -> str:
    return color(s, BLUE)


def red(s: str) -> str:
    return color(s, RED)


def green(s: str) -> str:
    return color(s, GREEN)


def magenta(s: str) -> str:
    return color(s, MAGENTA)


class TestResult:
    def __init__(self, description: str, input_file: str, expected_code: int, actual_code: int):
        self.input_file = input_file
        self.expected_code = expected_code
        self.actual_code = actual_code
        self.description = description

    def __str__(self):
        status = blue('PASSED') if self.expected_code == self.actual_code else f'{red('FAILED')} with {self.actual_code}'
        return f'{self.description} {self.input_file} {status}'

class Test:
    def __init__(self, description: str, code: int, show_stdout: bool, show_stderr: bool):
        self.description = description
        self.code = code
        self.show_stdout = show_stdout
        self.show_stderr = show_stderr
        self.tests: List[Path] = []
        self.text_inputs: List[str] = []

    def test(self, program: str, tests_dir: Path) -> Generator[TestResult, None, None]:
        for test in self.tests:
            file_name = str(tests_dir / test)

            with open(file_name, 'r', encoding='utf-8') as file:
                stdout_dev = None if self.show_stdout else subprocess.DEVNULL
                stderr_dev = None if self.show_stderr else subprocess.DEVNULL
                p = subprocess.run(['python', program], stdin=file, stdout=stdout_dev, stderr=stderr_dev)

            yield TestResult(self.description, file_name, self.code, p.returncode)

        for text in self.text_inputs:
            stdout_dev = None if self.show_stdout else subprocess.DEVNULL
            stderr_dev = None if self.show_stderr else subprocess.DEVNULL
            p = subprocess.run(['python', program], input=text.encode(), stdout=stdout_dev, stderr=stderr_dev)

            yield TestResult(self.description, '*text*', self.code, p.returncode)


class Tester:
    def __init__(self, program: Path, tests_dir: Path, *tests: Test):
        self.tests: List[Test] = list(tests)
        self.program = program
        self.tests_dir = tests_dir
        self.passed_count = 0
        self.failed_count = 0

    def test(self) -> Generator[TestResult, None, None]:
        for test in self.tests:
            for result in test.test(str(self.program), self.tests_dir):
                if result.actual_code == result.expected_code:
                    self.passed_count += 1
                else:
                    self.failed_count += 1

                yield result

    def result(self) -> str:
        count = sum(len(t.tests) for t in self.tests) + sum(len(t.text_inputs) for t in self.tests)
        text = f'passed {self.passed_count} / {count}'
        return green(text) if self.passed_count == count else magenta(text)


def main():
    with open('test.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    program = '.' / Path(data['app'])
    tests_dir = '.' / Path(data['input-directory'])

    tester = Tester(program, tests_dir)

    for test_dict in data['tests']:
        description = test_dict['description']
        code = int(test_dict['code'])

        if 'stderr' not in test_dict:
            show_stderr = True
        elif test_dict['stderr'] == 'show':
            show_stderr = True
        elif test_dict['stderr'] == 'hide':
            show_stderr = False
        else:
            raise ValueError()

        if 'stdout' not in test_dict:
            show_stdout = False
        elif test_dict['stdout'] == 'show':
            show_stdout = True
        elif test_dict['stdout'] == 'hide':
            show_stdout = False
        else:
            raise ValueError()

        test = Test(description, code, show_stdout, show_stderr)

        if 'files' in test_dict:
            test.tests.extend(Path(file) for file in test_dict['files'])

        if 'inputs' in test_dict:
            test.text_inputs.extend(test_dict['inputs'])

        tester.tests.append(test)

    for result in tester.test():
        print(result)

    print(tester.result())

main()
