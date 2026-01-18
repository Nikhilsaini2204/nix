"""Call graph builder and analyzer for tracing method calls."""

from typing import Dict, List, Optional, Any, Set


class CallGraph:
    """Build and analyze call graphs for Java methods."""

    def __init__(self):
        """Initialize the call graph."""
        # callers: method_fqn -> list of methods that call it
        self.callers: Dict[str, List[str]] = {}
        # callees: method_fqn -> list of methods it calls
        self.callees: Dict[str, List[str]] = {}
        # edges: list of (caller, callee) tuples
        self.edges: List[Dict[str, str]] = []
        # Method index for quick lookup
        self.methods: Dict[str, Dict] = {}

    def build_from_methods(self, methods: List[Dict], method_calls: List[Dict]) -> Dict[str, Any]:
        """Build call graph from parsed method information.

        Args:
            methods: List of method information dictionaries from parser
            method_calls: List of method call information dictionaries

        Returns:
            Dictionary with 'callers', 'callees', and 'edges'
        """
        self.callers = {}
        self.callees = {}
        self.edges = []
        self.methods = {}

        # Build method index
        for method in methods:
            fqn = method.get('fqn', '')
            if fqn:
                self.methods[fqn] = method
                # Also index by simple name for fuzzy matching
                simple_name = method.get('name', '')
                if simple_name:
                    key = f"{method.get('class_name', '')}.{simple_name}"
                    self.methods[key] = method

        # Build edges from method internal calls
        for method in methods:
            caller_fqn = method.get('fqn', '')
            if not caller_fqn:
                continue

            calls = method.get('calls', [])
            for callee_name in calls:
                # Try to resolve callee to full method
                callee_fqn = self._resolve_method_call(callee_name, method)

                if callee_fqn:
                    self._add_edge(caller_fqn, callee_fqn)

        return {
            'callers': self.callers,
            'callees': self.callees,
            'edges': self.edges
        }

    def load_from_data(self, data: Dict[str, Any]):
        """Load call graph from stored data.

        Args:
            data: Dictionary with 'callers', 'callees', 'edges'
        """
        self.callers = data.get('callers', {})
        self.callees = data.get('callees', {})
        self.edges = data.get('edges', [])

    def _add_edge(self, caller: str, callee: str):
        """Add a call edge to the graph.

        Args:
            caller: Fully qualified name of calling method
            callee: Fully qualified name of called method
        """
        # Add to callees map
        if caller not in self.callees:
            self.callees[caller] = []
        if callee not in self.callees[caller]:
            self.callees[caller].append(callee)

        # Add to callers map
        if callee not in self.callers:
            self.callers[callee] = []
        if caller not in self.callers[callee]:
            self.callers[callee].append(caller)

        # Add to edges
        edge = {'caller': caller, 'callee': callee}
        if edge not in self.edges:
            self.edges.append(edge)

    def _resolve_method_call(self, call_name: str, caller_method: Dict) -> Optional[str]:
        """Try to resolve a method call to a fully qualified name.

        Args:
            call_name: Simple method name being called
            caller_method: The method making the call (for context)

        Returns:
            Fully qualified name of the called method, or None if can't resolve
        """
        # Check if it's already in our index
        if call_name in self.methods:
            return self.methods[call_name].get('fqn')

        # Try with caller's class context
        caller_class = caller_method.get('class_fqn', '')
        if caller_class:
            candidate = f"{caller_class}.{call_name}"
            if candidate in self.methods:
                return candidate

        # Check for method with just the name
        for fqn, method in self.methods.items():
            if method.get('name') == call_name:
                return fqn

        # Can't resolve - return a placeholder
        return f"?.{call_name}"

    def get_callers(self, method_fqn: str) -> List[str]:
        """Get all methods that call a given method.

        Args:
            method_fqn: Fully qualified name of the method

        Returns:
            List of caller method FQNs
        """
        return self.callers.get(method_fqn, [])

    def get_callees(self, method_fqn: str) -> List[str]:
        """Get all methods called by a given method.

        Args:
            method_fqn: Fully qualified name of the method

        Returns:
            List of callee method FQNs
        """
        return self.callees.get(method_fqn, [])

    def trace_upstream(self, method_fqn: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """Trace all callers of a method recursively (upstream).

        This finds the path from entry points (controllers, etc.) to this method.

        Args:
            method_fqn: Fully qualified name of the target method
            max_depth: Maximum depth to trace

        Returns:
            List of call chains, each chain is a list of method FQNs
        """
        chains = []
        visited: Set[str] = set()

        def trace(method: str, current_chain: List[str], depth: int):
            if depth > max_depth:
                return
            if method in visited:
                # Cycle detected
                chains.append(current_chain + [method + " (cycle)"])
                return

            visited.add(method)
            callers = self.get_callers(method)

            if not callers:
                # This is an entry point (or we can't trace further)
                chains.append(current_chain + [method])
                return

            for caller in callers:
                trace(caller, current_chain + [method], depth + 1)

            visited.remove(method)

        trace(method_fqn, [], 0)
        return chains

    def trace_downstream(self, method_fqn: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """Trace all callees of a method recursively (downstream).

        This finds what methods are called from this method and deeper.

        Args:
            method_fqn: Fully qualified name of the starting method
            max_depth: Maximum depth to trace

        Returns:
            List of call chains, each chain is a list of method FQNs
        """
        chains = []
        visited: Set[str] = set()

        def trace(method: str, current_chain: List[str], depth: int):
            if depth > max_depth:
                return
            if method in visited:
                chains.append(current_chain + [method + " (cycle)"])
                return

            visited.add(method)
            callees = self.get_callees(method)

            if not callees:
                # This is a leaf method
                chains.append(current_chain + [method])
                return

            for callee in callees:
                trace(callee, current_chain + [method], depth + 1)

            visited.remove(method)

        trace(method_fqn, [], 0)
        return chains

    def find_path(self, from_method: str, to_method: str, max_depth: int = 10) -> Optional[List[str]]:
        """Find a call path between two methods.

        Args:
            from_method: Starting method FQN
            to_method: Target method FQN
            max_depth: Maximum path length

        Returns:
            List of method FQNs representing the path, or None if no path exists
        """
        visited: Set[str] = set()
        queue = [[from_method]]

        while queue:
            path = queue.pop(0)
            current = path[-1]

            if current == to_method:
                return path

            if len(path) > max_depth:
                continue

            if current in visited:
                continue

            visited.add(current)

            for callee in self.get_callees(current):
                if callee not in visited:
                    queue.append(path + [callee])

        return None

    def get_entry_points(self, methods: List[Dict] = None) -> List[str]:
        """Find methods that are likely entry points.

        Entry points are methods that:
        - Have no callers (within the project)
        - Or are annotated with Spring web annotations

        Args:
            methods: Optional list of method info dicts for annotation checking

        Returns:
            List of entry point method FQNs
        """
        entry_points = []

        # Web/API annotations that indicate entry points
        entry_annotations = {
            '@RequestMapping', '@GetMapping', '@PostMapping',
            '@PutMapping', '@DeleteMapping', '@PatchMapping',
            '@Scheduled', '@EventListener', '@KafkaListener',
            '@RabbitListener', '@JmsListener', '@PostConstruct'
        }

        # Check methods with no callers
        all_called_methods = set()
        for callee_list in self.callees.values():
            all_called_methods.update(callee_list)

        for method_fqn in self.callees.keys():
            if method_fqn not in all_called_methods:
                entry_points.append(method_fqn)

        # Also check annotation-based entry points
        if methods:
            for method in methods:
                annotations = set(method.get('annotations', []))
                if annotations & entry_annotations:
                    fqn = method.get('fqn', '')
                    if fqn and fqn not in entry_points:
                        entry_points.append(fqn)

        return entry_points

    def get_stats(self) -> Dict[str, int]:
        """Get call graph statistics.

        Returns:
            Dictionary with graph statistics
        """
        return {
            'total_methods': len(set(self.callers.keys()) | set(self.callees.keys())),
            'total_edges': len(self.edges),
            'methods_with_callers': len(self.callers),
            'methods_with_callees': len(self.callees)
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert call graph to dictionary for serialization.

        Returns:
            Dictionary representation of the call graph
        """
        return {
            'callers': self.callers,
            'callees': self.callees,
            'edges': self.edges
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CallGraph':
        """Create CallGraph from dictionary.

        Args:
            data: Dictionary with 'callers', 'callees', 'edges'

        Returns:
            CallGraph instance
        """
        graph = cls()
        graph.load_from_data(data)
        return graph
