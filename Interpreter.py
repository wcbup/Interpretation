from __future__ import annotations
from load_class_files import load_class_files
from typing import List, Dict, Union, Tuple
from enum import Enum
from copy import deepcopy
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
    INT = "Int"
    VOID = "Void"
    INT_ARRAY = "Int array"

    def __str__(self) -> str:
        return self.name


class JavaVariable:
    def __init__(self, value: int | None | Tuple[VariableType, int, List]) -> None:
        match value:
            case int():
                self.value = value
                self.type = VariableType.INT
            case None:
                self.value = None
                self.type = VariableType.VOID
            case tuple():
                array_type, length, array_values = value
                match array_type:
                    case VariableType.INT:
                        self.value = array_values
                        self.type = VariableType.INT_ARRAY
                        self.length = length
                        current_length = len(self.value)
                        if self.length > current_length:
                            self.value = self.value + [0] * (
                                self.length - current_length
                            )
                    case _:
                        raise Exception(
                            "Unsupported array type in JavaVariable", array_type
                        )

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
    def __init__(
        self, java_program: JavaProgram, init_peremeters: List[JavaVariable]
    ) -> None:
        self.java_program = java_program
        self.memory: Dict[str, JavaVariable] = {}
        self.stack: List[MethodStack] = []

        init_local_vars: Dict[int, JavaVariable] = {}
        for i in range(len(init_peremeters)):
            init_local_vars[i] = init_peremeters[i]
        init_method_stack = MethodStack(init_local_vars, self.java_program.init_method)
        self.stack.append(init_method_stack)

        self.return_value = JavaVariable(None)

    def step(self) -> bool:
        """
        return true indicates operation continues
        return false indicates operation ends
        """
        top_stack = self.stack[-1]
        operation_json = top_stack.program_counter.get_current_operation()
        opr_type: str = operation_json["opr"]
        match opr_type:
            case "return":
                return_type: str | None = operation_json["type"]
                match return_type:
                    case None:
                        return_value = JavaVariable(None)

                    case "int":
                        # push the return value to the invoker's stack
                        return_value = top_stack.operate_stack.pop()

                    case _:
                        raise Exception("Unsupported case in return_type:", return_type)

                if len(self.stack) > 1 and return_value.type != VariableType.VOID:
                    self.stack[-2].operate_stack.append(return_value)
                else:
                    self.return_value = return_value

                self.log_operation(f"{opr_type} {return_type}")

                # pop and return
                self.stack.pop()

            case "push":
                value_json: Dict[str, Union[int, str]] = operation_json["value"]
                value_type = value_json["type"]
                match value_type:
                    case "integer":
                        value_value: int = value_json["value"]
                        top_stack.operate_stack.append(JavaVariable(value_value))
                        self.log_operation(f"{opr_type} {value_value}")

                    case _:
                        raise Exception("Unsupported case in value_type:", value_type)

            case "load":
                load_type: str = operation_json["type"]
                match load_type:
                    case "int":
                        load_index: int = operation_json["index"]
                        top_stack.operate_stack.append(
                            deepcopy(top_stack.local_variables[load_index])
                        )
                        self.log_operation(
                            f"{opr_type}, type: {load_type}, index: {load_index}"
                        )

                    case "ref":
                        load_index: int = operation_json["index"]
                        top_stack.operate_stack.append(
                            top_stack.local_variables[load_index]
                        )
                        self.log_operation(
                            f"{opr_type}, type: {load_type}, index: {load_index}"
                        )

                    case _:
                        raise Exception("Unsupported case in load_type:", load_type)

            case "array_load":
                load_type: str = operation_json["type"]
                load_index: JavaVariable = top_stack.operate_stack.pop()
                array_ref = top_stack.operate_stack.pop()
                match load_type:
                    case "int":
                        result_value = JavaVariable(array_ref.value[load_index.value])
                        top_stack.operate_stack.append(result_value)
                        self.log_operation(
                            f"{opr_type}, {load_type}, {load_index.value}"
                        )
                    case _:
                        raise Exception("Unsupport type in array load:", load_type)

            case "array_store":
                array_value = top_stack.operate_stack.pop()
                array_index = top_stack.operate_stack.pop()
                array_ref = top_stack.operate_stack.pop()
                type_str: str = operation_json["type"]
                match type_str:
                    case "int":
                        array_ref.value[array_index.value] = array_value.value

                    case _:
                        raise Exception("Unsupported type in array store:", type_str)

                self.log_operation(f"{opr_type}, {type_str}")

            case "binary":
                binary_operant = operation_json["operant"]
                binary_type = operation_json["type"]
                operand_b = top_stack.operate_stack.pop()
                operand_a = top_stack.operate_stack.pop()

                match binary_operant:
                    case "add":
                        match binary_type:
                            case "int":
                                result = JavaVariable(operand_a.value + operand_b.value)
                                top_stack.operate_stack.append(result)
                                self.log_operation(
                                    f"add int: {operand_a.value}, {operand_b.value}"
                                )

                            case _:
                                raise Exception(
                                    "Unsupported case in add type:", binary_type
                                )

                    case "sub":
                        match binary_type:
                            case "int":
                                result = JavaVariable(operand_a.value - operand_b.value)
                                top_stack.operate_stack.append(result)
                                self.log_operation(
                                    f"sub int: {operand_a.value}, {operand_b.value}"
                                )

                            case _:
                                raise Exception(
                                    "Unsupported case in add type:", binary_type
                                )

                    case "mul":
                        match binary_type:
                            case "int":
                                result = JavaVariable(operand_a.value * operand_b.value)
                                top_stack.operate_stack.append(result)
                                self.log_operation(
                                    f"mul int: {operand_a.value}, {operand_b.value}"
                                )

                            case _:
                                raise Exception(
                                    "Unsupported case in mul type:", binary_type
                                )

                    case _:
                        raise Exception(
                            "Unsupported case in binary_operant:", binary_operant
                        )

            case "if":
                if_condition: str = operation_json["condition"]
                if_target: int = operation_json["target"]
                operand_b = top_stack.operate_stack.pop()
                operand_a = top_stack.operate_stack.pop()
                match if_condition:
                    case "gt":
                        if operand_a.value > operand_b.value:
                            top_stack.program_counter.index = if_target - 1

                        self.log_operation(
                            f"{opr_type}, condition: {if_condition}, target: {if_target}"
                        )

                    case "ge":
                        if operand_a.value >= operand_b.value:
                            top_stack.program_counter.index = if_target - 1

                        self.log_operation(
                            f"{opr_type}, condition: {if_condition}, target: {if_target}"
                        )
                    
                    case "lt":
                        if operand_a.value < operand_b.value:
                            top_stack.program_counter.index = if_target - 1

                        self.log_operation(
                            f"{opr_type}, condition: {if_condition}, target: {if_target}"
                        )

                    case "le":
                        if operand_a.value <= operand_b.value:
                            top_stack.program_counter.index = if_target - 1

                        self.log_operation(
                            f"{opr_type}, condition: {if_condition}, target: {if_target}"
                        )

                    case _:
                        raise Exception(
                            "Unsupported case in if condition:", if_condition
                        )

            case "store":
                store_type = operation_json["type"]
                store_index: int = operation_json["index"]
                store_value = top_stack.operate_stack.pop()
                match store_type:
                    case "int" | "ref":
                        top_stack.local_variables[store_index] = store_value
                        self.log_operation(f"{opr_type}, type: {store_type}")

                    case _:
                        raise Exception("Unsupported case in store type:", store_type)

            case "goto":
                goto_target: int = operation_json["target"]
                top_stack.program_counter.index = goto_target - 1
                self.log_operation(f"{opr_type}, target: {goto_target}")

            case "ifz":
                ifz_condition: str = operation_json["condition"]
                ifz_target: int = operation_json["target"]
                ifz_value = top_stack.operate_stack.pop()
                match ifz_condition:
                    case "gt":
                        if ifz_value.value > 0:
                            top_stack.program_counter.index = ifz_target - 1
                        self.log_operation(f"{opr_type}, {ifz_condition}, {ifz_target}")

                    case _:
                        raise Exception(
                            "Unsupported case in ifz_condition:", ifz_condition
                        )

            case "incr":
                incr_index: int = operation_json["index"]
                incr_amount: int = operation_json["amount"]
                incr_val = top_stack.local_variables[incr_index]
                incr_val.value += incr_amount
                self.log_operation(
                    f"{opr_type}, index: {incr_index}, amouont: {incr_amount}"
                )

            case "invoke":
                method_json = operation_json["method"]
                class_id: str = method_json["ref"]["name"]
                method_name: str = method_json["name"]
                new_method = self.java_program.java_class_dict[class_id].method_dict[
                    method_name
                ]
                args_json: List[str] = method_json["args"]
                parameter_dict: Dict[int, JavaVariable] = {}
                for i in range(len(args_json)):
                    parameter = top_stack.operate_stack.pop()
                    parameter_dict[i] = parameter
                new_method_stack = MethodStack(parameter_dict, new_method)
                self.stack.append(new_method_stack)

                self.log_operation(f"{opr_type}, {method_name}, args: {args_json}")

            case "newarray":
                dimension = operation_json["dim"]
                if dimension > 1:
                    raise Exception("Unsupport dim in newarray:", dimension)

                type_str: str = operation_json["type"]
                length = top_stack.operate_stack.pop().value
                match type_str:
                    case "int":
                        top_stack.operate_stack.append(
                            JavaVariable((VariableType.INT, length, []))
                        )

                    case _:
                        raise Exception("Unsupported type in newarray:", type_str)

                self.log_operation(f"{opr_type}, {type_str}, dim: {dimension}")
            
            case "arraylength":
                array_ref = top_stack.operate_stack.pop()
                top_stack.operate_stack.append(JavaVariable(array_ref.length))
                self.log_operation(opr_type)

            case "dup":
                top_variable = top_stack.operate_stack[-1]
                match top_variable.type:
                    case VariableType.INT:
                        top_stack.operate_stack.append(deepcopy(top_variable))
                    case VariableType.INT_ARRAY:
                        top_stack.operate_stack.append(top_variable)
                    case _:
                        raise Exception("Unsupported type in dup:", top_variable.type)

                self.log_operation(opr_type)

            case _:
                raise Exception("Unsupported case in opr_type:", opr_type)

        top_stack.program_counter.index += 1  # step 1
        if len(self.stack) > 0:
            return True
        else:
            return False

    def log_operation(self, log_str: str) -> None:
        print("Operation:", log_str)

    def run(self) -> None:
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
        var_str = ""
        for i in top_stack.local_variables.keys():
            var_str += f"{i}: {top_stack.local_variables[i]}"
            if i != len(top_stack.local_variables) - 1:
                var_str += ", "
        print(" ", "local varaibles:", f"{{{var_str}}}")
        print(
            " ",
            "operate stack:",
            f"[{', '.join(str(x) for x in top_stack.operate_stack)}]",
        )
        print(" ", "program counter index:", top_stack.program_counter.index)
        print()

    def log_done(self) -> None:
        print("---final state---")
        print("memory:", self.memory)
        print("stack size:", len(self.stack))
        print("return value:", str(self.return_value))


# test code
if __name__ == "__main__":
    java_program = JavaProgram(
        "course-02242-examples", "dtu/compute/exec/Array", "bubbleSort"
    )
    java_interpreter = Interpreter(java_program, [JavaVariable((VariableType.INT, 7, [5, 4, 3, 114, 514, 1919]))])
    java_interpreter.run()
