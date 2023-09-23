from __future__ import annotations
from load_class_files import load_class_files
from typing import List, Dict, Union
from enum import Enum
import json

JSON_CONTENT = Dict[str, Union[str, List[Union[str, Dict]], Dict]]


class JavaMethod:
    def __init__(self, json_content: JSON_CONTENT) -> None:
        self.json_content = json_content
        self.id = self.json_content["name"]
        self.bytecode_json: List[JSON_CONTENT] = json_content["code"]["bytecode"]


class JavaClass:
    def __init__(self, json_str: str) -> None:
        self.json_content: JSON_CONTENT = json.loads(json_str)
        self.id = self.json_content["name"]

        self.method_dict: Dict[str, JavaMethod] = {}
        for method_json in self.json_content["methods"]:
            # only handle method with "@Case"
            annotations_json: List[JSON_CONTENT] = method_json["annotations"]
            for annotation_json in annotations_json:
                if annotation_json["type"] == "dtu/compute/exec/Case":
                    java_method = JavaMethod(method_json)
                    self.method_dict[java_method.id] = java_method
                    break


class VariableType(Enum):
    INT = "integer"


class JavaVariable:
    def __init__(self, value: int) -> None:
        match value:
            case int():
                self.value = value
                self.type = VariableType.INT
            case _:
                raise Exception("Unsupported type in JavaVariable", value)
    
    def __str__(self) -> str:
        return f"{str(self.type)}: {self.value}"


class ProgramCounter:
    def __init__(self, java_method: JavaMethod) -> None:
        self.index = 0
        self.java_method = java_method

    def get_current_operation(self) -> JSON_CONTENT:
        return self.java_method.bytecode_json[self.index]


class MethodStack:
    def __init__(
        self, parameters: Dict[int, JavaVariable], java_method: JavaMethod
    ) -> None:
        self.local_variables = parameters
        self.operate_stack: List[JavaVariable] = []
        self.program_counter = ProgramCounter(java_method)


class JavaProgram:
    def __init__(
        self, project_name: str, init_class_name: str, init_method_name: str
    ) -> None:
        self.java_class_dict: Dict[str, JavaClass] = {}
        for json_str in load_class_files(project_name):
            java_class = JavaClass(json_str)
            self.java_class_dict[java_class.id] = java_class

        self.init_class_name = init_class_name
        self.init_method_name = init_method_name
        self.init_method = self.java_class_dict[init_class_name].method_dict[
            init_method_name
        ]


class Interpreter:
    def __init__(self, java_program: JavaProgram) -> None:
        self.java_program = java_program
        self.memory: Dict[str, JavaVariable] = {}
        self.stack: List[MethodStack] = []

    def step(self) -> bool:
        """
        return true indicates operation continues
        return false indicates operation ends
        """
        method_stack = self.stack[-1]
        operation_json = method_stack.program_counter.get_current_operation()
        opr_type: str = operation_json["opr"]
        match opr_type:
            case "return":
                return_type: str | None = operation_json["type"]
                match return_type:
                    case None:
                        self.log_operation(opr_type + " " + "Void")
                    case _:
                        raise Exception("Unsupported case in return_type:", return_type)
                
                # pop and return
                self.stack.pop()

            case "push":
                value_json: Dict[str, Union[int, str]] = operation_json["value"]
                value_type = value_json["type"]
                match value_type:
                    case "integer":
                        value_value: int = value_json["value"]
                        self.stack[-1].operate_stack.append(JavaVariable(value_value))
                    case _:
                        raise Exception("Unsupported case in value_type:", value_type)

                self.stack[-1].program_counter.index += 1 # step 1

            case _:
                raise Exception("Unsupported case in opr_type:", opr_type)
        
        if len(self.stack) > 0:
            return True
        else:
            return False
        

    def log_operation(self, log_str: str) -> None:
        print("Operation:", log_str)

    def run(self) -> None:
        init_method_stack = MethodStack({}, self.java_program.init_method)
        self.stack.append(init_method_stack)
        self.log_start()
        self.log_state()
        while self.step():
            self.log_state()
        self.log_done()

    def log_start(self) -> None:
        print("---starting program---")
        print("init class:", self.java_program.init_class_name)
        print("init method:", self.java_program.init_method_name)
        print()

    def log_state(self) -> None:
        print("---state---")
        print("memory:", self.memory)
        print("stack size:", len(self.stack))
        print("top stack:")
        top_stack = self.stack[-1]
        print(" ", "local varaibles:", top_stack.local_variables)
        print(" ", "operate stack:", ", ".join(str(x) for x in top_stack.operate_stack))
        print(" ", "program counter index:", top_stack.program_counter.index)
        print()
    
    def log_done(self) -> None:
        print("---final state---")
        print("memory:", self.memory)
        print("stack size:", len(self.stack))


# test code
if __name__ == "__main__":
    java_program = JavaProgram(
        "course-02242-examples", "dtu/compute/exec/Simple", "noop"
    )
    java_interpreter = Interpreter(java_program)
    java_interpreter.run()