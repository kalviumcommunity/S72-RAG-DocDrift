import re
from typing import List, Dict, Any

class MarkdownParser:
    """
    Specialized parser for Markdown files that preserves heading hierarchy 
    and groups content into chunks based on sections.
    """
    def __init__(self):
        # Match markdown headers: # to ######
        self.header_pattern = re.compile(r'^(#{1,6})\s+(.*)')

    def parse(self, text: str) -> List[Dict[str, Any]]:
        lines = text.split('\n')
        chunks = []
        
        current_headers = {}
        current_chunk_content = []
        current_start_line = 1
        current_level = 0
        
        def save_chunk(end_line: int):
            if current_chunk_content and any(line.strip() for line in current_chunk_content):
                content = '\n'.join(current_chunk_content).strip()
                if content:
                    tags = ['markdown']
                    # Add current hierarchy headers as tags
                    tags.extend([h for k, h in sorted(current_headers.items()) if h])
                    
                    chunks.append({
                        'section_header': current_headers.get(current_level, ""),
                        'section_level': current_level,
                        'start_line': current_start_line,
                        'end_line': end_line,
                        'content': content,
                        'tags': tags
                    })

        for i, line in enumerate(lines):
            line_num = i + 1
            header_match = self.header_pattern.match(line)
            
            if header_match:
                save_chunk(line_num - 1)
                
                level = len(header_match.group(1))
                header_text = header_match.group(2).strip()
                
                # Clear deeper headers from the hierarchy
                keys_to_remove = [k for k in current_headers.keys() if k >= level]
                for k in keys_to_remove:
                    del current_headers[k]
                    
                current_headers[level] = header_text
                current_level = level
                
                current_chunk_content = [line]
                current_start_line = line_num
            else:
                current_chunk_content.append(line)
                
        # Save last chunk
        save_chunk(len(lines))
        
        return chunks
