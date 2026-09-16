import json
from typing import List, Dict, Any

class OpenAPIParser:
    """
    Specialized parser for OpenAPI/Swagger specifications that extracts
    endpoints, HTTP methods, and parameters into semantically meaningful chunks.
    """
    def parse(self, text: str, format_type: str = "json") -> List[Dict[str, Any]]:
        chunks = []
        try:
            if format_type == "json":
                data = json.loads(text)
            else:
                import yaml
                data = yaml.safe_load(text)
        except Exception as e:
            raise ValueError(f"Failed to parse OpenAPI document: {e}")
            
        lines = text.split('\n')
        paths = data.get('paths', {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() not in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                    continue
                    
                # Approximate line number finding by scanning the raw text
                start_line = 1
                for i, line in enumerate(lines):
                    if f'"{path}"' in line or f"'{path}'" in line:
                        for j in range(i, min(i+15, len(lines))):
                            if f'"{method}"' in line or f"'{method}'" in line or method in line:
                                start_line = j + 1
                                break
                        break
                        
                summary = operation.get('summary', '')
                description = operation.get('description', '')
                parameters = operation.get('parameters', [])
                
                content_parts = [f"Endpoint: {method.upper()} {path}"]
                if summary: 
                    content_parts.append(f"Summary: {summary}")
                if description: 
                    content_parts.append(f"Description: {description}")
                
                if parameters:
                    content_parts.append("Parameters:")
                    for param in parameters:
                        p_name = param.get('name', 'unknown')
                        p_in = param.get('in', 'unknown')
                        p_req = "required" if param.get('required') else "optional"
                        content_parts.append(f"  - {p_name} ({p_in}, {p_req})")
                        
                chunks.append({
                    'section_header': f"{method.upper()} {path}",
                    'section_level': 2,
                    'start_line': start_line,
                    'end_line': start_line + len(content_parts) - 1, # Approximate block size
                    'content': '\n'.join(content_parts),
                    'tags': ['openapi', 'endpoint', method.upper()],
                    'http_method': method.upper(),
                    'path': path
                })
                
        return chunks
