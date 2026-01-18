"""Java code parser using tree-sitter for accurate AST parsing."""

import os
from typing import Dict, List, Optional, Any

try:
    import tree_sitter_java as tsjava
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


class JavaParser:
    """Parse Java files using tree-sitter for accurate AST analysis."""

    def __init__(self):
        """Initialize the Java parser."""
        self.parser = None
        self.language = None
        self._init_parser()

    def _init_parser(self):
        """Initialize tree-sitter parser with Java language."""
        if not TREE_SITTER_AVAILABLE:
            return

        try:
            self.language = Language(tsjava.language())
            self.parser = Parser(self.language)
        except Exception:
            self.parser = None
            self.language = None

    def is_available(self) -> bool:
        """Check if tree-sitter is available."""
        return self.parser is not None

    def parse_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse a Java file and extract structural information.

        Args:
            file_path: Path to the Java file

        Returns:
            Dictionary with parsed information or None if parsing fails
        """
        if not self.is_available():
            return self._fallback_parse(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            tree = self.parser.parse(bytes(content, 'utf-8'))
            return self._extract_info(tree.root_node, content, file_path)
        except Exception:
            return self._fallback_parse(file_path)

    def _extract_info(self, root_node, content: str, file_path: str) -> Dict[str, Any]:
        """Extract structural information from the AST.

        Args:
            root_node: Root node of the AST
            content: File content
            file_path: Path to the file

        Returns:
            Dictionary with classes, methods, fields, annotations, method_calls
        """
        result = {
            'file_path': file_path,
            'package': None,
            'imports': [],
            'classes': [],
            'methods': [],
            'fields': [],
            'annotations': [],
            'method_calls': []
        }

        lines = content.split('\n')

        # Extract package
        package_node = self._find_node(root_node, 'package_declaration')
        if package_node:
            result['package'] = self._get_package_name(package_node, content)

        # Extract imports
        for imp in self._find_all_nodes(root_node, 'import_declaration'):
            result['imports'].append(self._get_node_text(imp, content))

        # Extract classes
        for class_node in self._find_all_nodes(root_node, ['class_declaration', 'interface_declaration', 'enum_declaration']):
            class_info = self._extract_class_info(class_node, content, lines, file_path, result['package'])
            result['classes'].append(class_info)
            result['methods'].extend(class_info.get('methods', []))
            result['fields'].extend(class_info.get('fields', []))

        # Extract all method calls for call graph
        for call_node in self._find_all_nodes(root_node, 'method_invocation'):
            call_info = self._extract_method_call(call_node, content, lines, file_path)
            if call_info:
                result['method_calls'].append(call_info)

        return result

    def _extract_class_info(self, class_node, content: str, lines: List[str],
                           file_path: str, package: Optional[str]) -> Dict[str, Any]:
        """Extract information about a class/interface/enum."""
        class_type = class_node.type
        name_node = self._find_node(class_node, 'identifier')
        class_name = self._get_node_text(name_node, content) if name_node else 'Unknown'

        start_line = class_node.start_point[0] + 1
        end_line = class_node.end_point[0] + 1

        # Extract annotations
        annotations = []
        modifiers = self._find_node(class_node.parent, 'modifiers') if class_node.parent else None
        if modifiers:
            for ann in self._find_all_nodes(modifiers, 'annotation'):
                ann_name = self._get_annotation_name(ann, content)
                if ann_name:
                    annotations.append(ann_name)

        # Also check directly before class node for annotations
        for ann in self._find_all_nodes(class_node, 'annotation'):
            ann_name = self._get_annotation_name(ann, content)
            if ann_name:
                annotations.append(ann_name)

        # Build full qualified name
        fqn = f"{package}.{class_name}" if package else class_name

        class_info = {
            'name': class_name,
            'fqn': fqn,
            'type': class_type.replace('_declaration', ''),
            'file_path': file_path,
            'start_line': start_line,
            'end_line': end_line,
            'annotations': annotations,
            'methods': [],
            'fields': [],
            'extends': None,
            'implements': []
        }

        # Extract superclass
        superclass = self._find_node(class_node, 'superclass')
        if superclass:
            type_node = self._find_node(superclass, 'type_identifier')
            if type_node:
                class_info['extends'] = self._get_node_text(type_node, content)

        # Extract interfaces
        interfaces = self._find_node(class_node, 'super_interfaces')
        if interfaces:
            for type_node in self._find_all_nodes(interfaces, 'type_identifier'):
                class_info['implements'].append(self._get_node_text(type_node, content))

        # Extract methods
        body = self._find_node(class_node, 'class_body') or self._find_node(class_node, 'interface_body')
        if body:
            for method_node in self._find_all_nodes(body, ['method_declaration', 'constructor_declaration']):
                method_info = self._extract_method_info(method_node, content, lines, file_path, class_name, fqn)
                class_info['methods'].append(method_info)

            # Extract fields
            for field_node in self._find_all_nodes(body, 'field_declaration'):
                field_info = self._extract_field_info(field_node, content, lines, file_path, class_name)
                class_info['fields'].append(field_info)

        return class_info

    def _extract_method_info(self, method_node, content: str, lines: List[str],
                            file_path: str, class_name: str, class_fqn: str) -> Dict[str, Any]:
        """Extract information about a method."""
        is_constructor = method_node.type == 'constructor_declaration'

        if is_constructor:
            name_node = self._find_node(method_node, 'identifier')
        else:
            name_node = self._find_node(method_node, 'identifier')

        method_name = self._get_node_text(name_node, content) if name_node else 'unknown'

        start_line = method_node.start_point[0] + 1
        end_line = method_node.end_point[0] + 1

        # Extract annotations
        annotations = []
        modifiers = self._find_node(method_node, 'modifiers')
        if modifiers:
            for ann in self._find_all_nodes(modifiers, 'annotation'):
                ann_name = self._get_annotation_name(ann, content)
                if ann_name:
                    annotations.append(ann_name)

        # Extract parameters
        params = []
        params_node = self._find_node(method_node, 'formal_parameters')
        if params_node:
            for param in self._find_all_nodes(params_node, 'formal_parameter'):
                type_node = self._find_first_child_by_types(param, ['type_identifier', 'generic_type', 'array_type', 'integral_type', 'floating_point_type', 'boolean_type'])
                name_n = self._find_node(param, 'identifier')
                if type_node and name_n:
                    params.append({
                        'type': self._get_node_text(type_node, content),
                        'name': self._get_node_text(name_n, content)
                    })

        # Extract return type
        return_type = None
        if not is_constructor:
            type_node = self._find_first_child_by_types(method_node, ['type_identifier', 'generic_type', 'array_type', 'void_type', 'integral_type', 'floating_point_type', 'boolean_type'])
            if type_node:
                return_type = self._get_node_text(type_node, content)

        # Extract method calls within this method
        internal_calls = []
        body = self._find_node(method_node, 'block')
        if body:
            for call in self._find_all_nodes(body, 'method_invocation'):
                call_name = self._get_method_call_name(call, content)
                if call_name:
                    internal_calls.append(call_name)

        return {
            'name': method_name,
            'fqn': f"{class_fqn}.{method_name}",
            'class_name': class_name,
            'class_fqn': class_fqn,
            'file_path': file_path,
            'start_line': start_line,
            'end_line': end_line,
            'is_constructor': is_constructor,
            'annotations': annotations,
            'parameters': params,
            'return_type': return_type,
            'calls': internal_calls
        }

    def _extract_field_info(self, field_node, content: str, lines: List[str],
                           file_path: str, class_name: str) -> Dict[str, Any]:
        """Extract information about a field."""
        # Get type
        type_node = self._find_first_child_by_types(field_node, ['type_identifier', 'generic_type', 'array_type', 'integral_type', 'floating_point_type', 'boolean_type'])
        field_type = self._get_node_text(type_node, content) if type_node else 'unknown'

        # Get name
        declarator = self._find_node(field_node, 'variable_declarator')
        name_node = self._find_node(declarator, 'identifier') if declarator else None
        field_name = self._get_node_text(name_node, content) if name_node else 'unknown'

        start_line = field_node.start_point[0] + 1

        # Extract annotations
        annotations = []
        modifiers = self._find_node(field_node, 'modifiers')
        if modifiers:
            for ann in self._find_all_nodes(modifiers, 'annotation'):
                ann_name = self._get_annotation_name(ann, content)
                if ann_name:
                    annotations.append(ann_name)

        return {
            'name': field_name,
            'type': field_type,
            'class_name': class_name,
            'file_path': file_path,
            'line': start_line,
            'annotations': annotations
        }

    def _extract_method_call(self, call_node, content: str, lines: List[str],
                            file_path: str) -> Optional[Dict[str, Any]]:
        """Extract information about a method call."""
        call_name = self._get_method_call_name(call_node, content)
        if not call_name:
            return None

        # Get the object/class the method is called on
        caller_object = None
        first_child = call_node.children[0] if call_node.children else None
        if first_child and first_child.type in ['identifier', 'field_access', 'method_invocation']:
            caller_object = self._get_node_text(first_child, content)

        return {
            'method_name': call_name,
            'caller_object': caller_object,
            'file_path': file_path,
            'line': call_node.start_point[0] + 1
        }

    def _get_method_call_name(self, call_node, content: str) -> Optional[str]:
        """Get the name of a method being called."""
        # Find the identifier that is the method name (usually last identifier before args)
        for child in call_node.children:
            if child.type == 'identifier':
                return self._get_node_text(child, content)

        # For chained calls, look deeper
        if call_node.children:
            last_id = None
            for child in call_node.children:
                if child.type == 'identifier':
                    last_id = self._get_node_text(child, content)
            return last_id

        return None

    def _get_annotation_name(self, ann_node, content: str) -> Optional[str]:
        """Get the name of an annotation."""
        name_node = self._find_node(ann_node, 'identifier')
        if name_node:
            return '@' + self._get_node_text(name_node, content)

        # Handle qualified names like @org.springframework.stereotype.Service
        scoped = self._find_node(ann_node, 'scoped_identifier')
        if scoped:
            return '@' + self._get_node_text(scoped, content)

        return None

    def _get_package_name(self, package_node, content: str) -> Optional[str]:
        """Extract package name from package declaration."""
        scoped = self._find_node(package_node, 'scoped_identifier')
        if scoped:
            return self._get_node_text(scoped, content)

        id_node = self._find_node(package_node, 'identifier')
        if id_node:
            return self._get_node_text(id_node, content)

        return None

    def _find_node(self, node, node_type: str):
        """Find the first child node of a specific type."""
        if node is None:
            return None

        for child in node.children:
            if child.type == node_type:
                return child
            result = self._find_node(child, node_type)
            if result:
                return result
        return None

    def _find_all_nodes(self, node, node_types) -> List:
        """Find all descendant nodes of specific types."""
        if isinstance(node_types, str):
            node_types = [node_types]

        results = []
        if node is None:
            return results

        for child in node.children:
            if child.type in node_types:
                results.append(child)
            results.extend(self._find_all_nodes(child, node_types))

        return results

    def _find_first_child_by_types(self, node, types: List[str]):
        """Find first direct child matching any of the types."""
        if node is None:
            return None
        for child in node.children:
            if child.type in types:
                return child
        return None

    def _get_node_text(self, node, content: str) -> str:
        """Get the text content of a node."""
        if node is None:
            return ''
        return content[node.start_byte:node.end_byte]

    def _fallback_parse(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Fallback regex-based parsing when tree-sitter is not available."""
        import re

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return None

        lines = content.split('\n')
        result = {
            'file_path': file_path,
            'package': None,
            'imports': [],
            'classes': [],
            'methods': [],
            'fields': [],
            'annotations': [],
            'method_calls': []
        }

        # Extract package
        pkg_match = re.search(r'package\s+([\w.]+)\s*;', content)
        if pkg_match:
            result['package'] = pkg_match.group(1)

        # Extract imports
        for match in re.finditer(r'import\s+([\w.*]+)\s*;', content):
            result['imports'].append(match.group(1))

        # Extract classes (basic regex)
        class_pattern = r'(?:@\w+(?:\([^)]*\))?\s*)*(?:public|private|protected)?\s*(?:abstract|final)?\s*(?:class|interface|enum)\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            start_pos = match.start()
            line_num = content[:start_pos].count('\n') + 1

            fqn = f"{result['package']}.{class_name}" if result['package'] else class_name

            class_info = {
                'name': class_name,
                'fqn': fqn,
                'type': 'class',
                'file_path': file_path,
                'start_line': line_num,
                'end_line': line_num,
                'annotations': [],
                'methods': [],
                'fields': [],
                'extends': None,
                'implements': []
            }

            # Extract annotations before class
            ann_pattern = r'@(\w+)'
            class_text = content[max(0, start_pos - 500):start_pos]
            for ann_match in re.finditer(ann_pattern, class_text):
                class_info['annotations'].append('@' + ann_match.group(1))

            result['classes'].append(class_info)

        # Extract methods (basic regex)
        method_pattern = r'(?:@\w+(?:\([^)]*\))?\s*)*(?:public|private|protected)?\s*(?:static|final|abstract|synchronized)?\s*(?:<[\w<>,\s]+>\s*)?(\w+)\s+(\w+)\s*\([^)]*\)'
        for match in re.finditer(method_pattern, content):
            return_type = match.group(1)
            method_name = match.group(2)

            # Skip if it looks like a class declaration
            if return_type in ('class', 'interface', 'enum', 'new', 'if', 'while', 'for', 'switch'):
                continue

            start_pos = match.start()
            line_num = content[:start_pos].count('\n') + 1

            # Find which class this method belongs to
            class_name = 'Unknown'
            for cls in result['classes']:
                if cls['start_line'] <= line_num:
                    class_name = cls['name']

            class_fqn = f"{result['package']}.{class_name}" if result['package'] else class_name

            method_info = {
                'name': method_name,
                'fqn': f"{class_fqn}.{method_name}",
                'class_name': class_name,
                'class_fqn': class_fqn,
                'file_path': file_path,
                'start_line': line_num,
                'end_line': line_num,
                'is_constructor': False,
                'annotations': [],
                'parameters': [],
                'return_type': return_type,
                'calls': []
            }

            # Extract annotations
            ann_pattern = r'@(\w+)'
            method_text = content[max(0, start_pos - 200):start_pos]
            for ann_match in re.finditer(ann_pattern, method_text):
                method_info['annotations'].append('@' + ann_match.group(1))

            result['methods'].append(method_info)

        return result
