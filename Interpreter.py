from __future__ import annotations
from load_class_files import load_class_files
from typing import List, Dict, Union
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


class JavaVariable:
    def __init__(self) -> None:
        pass


class ProgramCounter:
    def __init__(self, java_method: JavaMethod) -> None:
        self.index = 0
        self.java_method = java_method


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
        
        # print(self.java_class_dict[init_class_name].method_dict[init_method_name].bytecode_json)
    


class Interpreter:
    def __init__(self) -> None:
        pass


# test code
if __name__ == "__main__":
    java_program = JavaProgram("course-02242-examples", "dtu/compute/exec/Simple", "noop")
    
