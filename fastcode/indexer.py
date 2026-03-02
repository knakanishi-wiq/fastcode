"""
Code Indexer - Multi-level indexing of code repositories
"""

import hashlib
import logging
import os
import sqlite3
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from tqdm import tqdm
import pathspec

from .loader import RepositoryLoader
from .parser import CodeParser, FileParseResult
from .embedder import CodeEmbedder
from .repo_overview import RepositoryOverviewGenerator
from .utils import count_tokens, normalize_path
from .vector_store import VectorStore
from .db import init_db

logger = logging.getLogger(__name__)

@dataclass
class CodeElement:
    """Unified code element for indexing"""
    id: str
    type: str  # file, class, function, documentation
    name: str
    file_path: str
    relative_path: str
    language: str
    start_line: int
    end_line: int
    code: str
    signature: Optional[str]
    docstring: Optional[str]
    summary: Optional[str]
    metadata: Dict[str, Any]
    repo_name: Optional[str] = None  # Repository identifier
    repo_url: Optional[str] = None   # Repository URL (if available)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CodeIndexer:
    """Index code repository at multiple levels"""
    
    def __init__(self, config: Dict[str, Any], loader: RepositoryLoader, 
                 parser: CodeParser, embedder: CodeEmbedder, vector_store: Optional[VectorStore] = None):
        self.config = config
        self.indexing_config = config.get("indexing", {})
        self.logger = logging.getLogger(__name__)
        
        self.loader = loader
        self.parser = parser
        self.embedder = embedder
        self.vector_store = vector_store
        
        self.levels = self.indexing_config.get("levels", ["file", "class", "function", "documentation"])
        self.include_imports = self.indexing_config.get("include_imports", True)
        self.include_class_context = self.indexing_config.get("include_class_context", True)
        self.generate_repo_overview = self.indexing_config.get("generate_repo_overview", True)
        
        self.elements: List[CodeElement] = []
        
        # Repository identification
        self.current_repo_name: Optional[str] = None
        self.current_repo_url: Optional[str] = None
        
        # Repository overview generator
        self.overview_generator = RepositoryOverviewGenerator(config) if self.generate_repo_overview else None
    
    def index_repository(self, repo_name: Optional[str] = None, repo_url: Optional[str] = None) -> List[CodeElement]:
        """
        Index entire repository at multiple levels
        
        Args:
            repo_name: Optional repository name for identification
            repo_url: Optional repository URL for identification
        
        Returns:
            List of indexed code elements
        """
        self.logger.info("Starting repository indexing")
        
        # Set current repository information
        self.current_repo_name = repo_name
        self.current_repo_url = repo_url
        
        # Scan files
        files = self.loader.scan_files()
        self.logger.info(f"Indexing {len(files)} files for repository: {repo_name or 'Unknown'}")
        
        self.elements = []
        
        # Generate repository overview (for multi-repo support)
        # Store separately, not in self.elements
        if self.overview_generator and self.loader.repo_path:
            try:
                file_structure = self.overview_generator.parse_file_structure(
                    self.loader.repo_path, files
                )
                repo_overview = self.overview_generator.generate_overview(
                    self.loader.repo_path, repo_name or "Unknown", file_structure
                )
                
                # Save repository overview to separate storage
                self._save_repository_overview(repo_overview)
                self.logger.info(f"Generated and saved repository overview for {repo_name}")
            except Exception as e:
                self.logger.warning(f"Failed to generate repository overview: {e}")
        
        # Process each file
        for file_info in tqdm(files, desc="Indexing files"):
            file_path = file_info["path"]
            
            # Read content
            content = self.loader.read_file_content(file_path)
            if content is None:
                continue
            
            # Parse file
            parse_result = self.parser.parse_file(file_path, content)
            if parse_result is None:
                continue
            
            # Index at different levels
            self._index_file(file_info, content, parse_result)
        
        self.logger.info(f"Indexed {len(self.elements)} code elements for {repo_name or 'Unknown'}")
        
        # Generate embeddings
        self.logger.info("Generating embeddings for code elements")
        element_dicts = [elem.to_dict() for elem in self.elements]
        elements_with_embeddings = self.embedder.embed_code_elements(element_dicts)
        
        # Update elements with embeddings
        for elem, elem_dict in zip(self.elements, elements_with_embeddings):
            elem.metadata["embedding"] = elem_dict.get("embedding")
            elem.metadata["embedding_text"] = elem_dict.get("embedding_text")
        
        self.logger.info(f"✓ Repository indexing completed for {repo_name or 'Unknown'}: {len(self.elements)} elements indexed with embeddings")
        
        return self.elements
    
    def _index_file(self, file_info: Dict[str, Any], content: str, 
                    parse_result: FileParseResult):
        """Index a single file at multiple levels"""
        file_path = file_info["path"]
        relative_path = file_info["relative_path"]
        
        # File level
        if "file" in self.levels:
            self._add_file_level_element(file_info, content, parse_result)
        
        # Class level
        if "class" in self.levels:
            for class_info in parse_result.classes:
                self._add_class_level_element(
                    file_path, relative_path, content, parse_result, class_info
                )
        
        # Function level
        if "function" in self.levels:
            # 1. Top-level functions
            for func_info in parse_result.functions:
                self._add_function_level_element(
                    file_path, relative_path, content, parse_result, func_info
                )
            
            self.logger.debug(f"[DEBUG INDEXER] Processing methods for file: {file_info['path']}")
            # 2. Methods from classes (FIX APPLIED HERE)
            for class_info in parse_result.classes:
                self.logger.debug(f"[DEBUG INDEXER] Checking class '{class_info.name}' with {len(class_info.methods)} methods")
                # Now we iterate over the FunctionInfo objects we extracted
                for method_info in class_info.methods:
                    if isinstance(method_info, str):
                        self.logger.debug(f"[DEBUG INDEXER] ❌ ERROR: Method '{method_info}' is a STRING, not FunctionInfo object!")
                        self.logger.debug(f"               (You missed the fix in parser.py or indexer.py)")
                    else:
                        self.logger.debug(f"[DEBUG INDEXER] Indexing method: {class_info.name}.{method_info.name}")
                    
                    self._add_function_level_element(
                        file_path, relative_path, content, parse_result, method_info
                    )

        # Documentation level
        if "documentation" in self.levels:
            if parse_result.module_docstring:
                self._add_documentation_element(
                    file_path, relative_path, parse_result
                )
    
    def _add_file_level_element(self, file_info: Dict[str, Any], content: str,
                                 parse_result: FileParseResult):
        """Add file-level index element"""
        file_path = file_info["path"]
        relative_path = file_info["relative_path"]
        
        # Generate file summary
        summary = self._generate_file_summary(parse_result)
        
        # Create element
        element = CodeElement(
            id=self._generate_id("file", relative_path),
            type="file",
            name=relative_path,
            file_path=file_path,
            relative_path=relative_path,
            language=parse_result.language,
            start_line=1,
            end_line=parse_result.total_lines,
            code=content[:],  # First all chars for context
            signature=None,
            docstring=parse_result.module_docstring,
            summary=summary,
            metadata={
                "size": file_info["size"],
                "extension": file_info["extension"],
                "total_lines": parse_result.total_lines,
                "code_lines": parse_result.code_lines,
                "comment_lines": parse_result.comment_lines,
                "num_classes": len(parse_result.classes),
                "num_functions": len(parse_result.functions),
                "num_imports": len(parse_result.imports),
                "imports": [imp.to_dict() for imp in parse_result.imports] if self.include_imports else [],
            },
            repo_name=self.current_repo_name,
            repo_url=self.current_repo_url
        )
        
        self.elements.append(element)
    
    def _add_class_level_element(self, file_path: str, relative_path: str,
                                  content: str, parse_result: FileParseResult,
                                  class_info: Any):
        """Add class-level index element"""
        # Extract class code
        class_code = self._extract_lines(content, class_info.start_line, class_info.end_line)
        
        # Generate signature
        signature = f"class {class_info.name}"
        if class_info.bases:
            signature += f"({', '.join(class_info.bases)})"
        
        # Generate summary
        summary = f"Class {class_info.name} with {len(class_info.methods)} methods"
        if class_info.bases:
            summary += f", inherits from {', '.join(class_info.bases)}"
        
        element = CodeElement(
            id=self._generate_id("class", relative_path, class_info.name),
            type="class",
            name=class_info.name,
            file_path=file_path,
            relative_path=relative_path,
            language=parse_result.language,
            start_line=class_info.start_line,
            end_line=class_info.end_line,
            code=class_code,
            signature=signature,
            docstring=class_info.docstring,
            summary=summary,
            metadata={
                "bases": class_info.bases,
                # Convert back to list of names for metadata to keep it clean
                "methods": [m.name for m in class_info.methods], 
                "decorators": class_info.decorators,
                "num_methods": len(class_info.methods),
            },
            repo_name=self.current_repo_name,
            repo_url=self.current_repo_url
        )
        
        self.elements.append(element)
    
    def _add_function_level_element(self, file_path: str, relative_path: str,
                                     content: str, parse_result: FileParseResult,
                                     func_info: Any):
        """Add function-level index element"""
        # Extract function code
        func_code = self._extract_lines(content, func_info.start_line, func_info.end_line)
        
        # Generate signature
        signature = f"{'async ' if func_info.is_async else ''}def {func_info.name}"
        signature += f"({', '.join(func_info.parameters)})"
        if func_info.return_type:
            signature += f" -> {func_info.return_type}"
        
        # Generate summary
        summary = f"Function {func_info.name}"
        if func_info.parameters:
            summary += f" with {len(func_info.parameters)} parameters"
        
        id_parts = [relative_path]
        if func_info.class_name:
            id_parts.append(func_info.class_name)
        id_parts.append(func_info.name)
        
        generated_id = self._generate_id("function", *id_parts)
        
        element = CodeElement(
            id=generated_id,
            type="function",
            name=func_info.name,
            file_path=file_path,
            relative_path=relative_path,
            language=parse_result.language,
            start_line=func_info.start_line,
            end_line=func_info.end_line,
            code=func_code,
            signature=signature,
            docstring=func_info.docstring,
            summary=summary,
            metadata={
                "parameters": func_info.parameters,
                "return_type": func_info.return_type,
                "is_async": func_info.is_async,
                "is_method": func_info.is_method,
                "class_name": func_info.class_name,
                "decorators": func_info.decorators,
                "complexity": func_info.complexity,
            },
            repo_name=self.current_repo_name,
            repo_url=self.current_repo_url
        )
        
        self.elements.append(element)
    
    def _add_documentation_element(self, file_path: str, relative_path: str,
                                    parse_result: FileParseResult):
        """Add documentation-level index element"""
        element = CodeElement(
            id=self._generate_id("doc", relative_path),
            type="documentation",
            name=f"Documentation: {relative_path}",
            file_path=file_path,
            relative_path=relative_path,
            language=parse_result.language,
            start_line=1,
            end_line=1,
            code="",
            signature=None,
            docstring=parse_result.module_docstring,
            summary=f"Module documentation for {relative_path}",
            metadata={
                "is_module_doc": True,
            },
            repo_name=self.current_repo_name,
            repo_url=self.current_repo_url
        )
        
        self.elements.append(element)
    
    def _save_repository_overview(self, repo_overview: Dict[str, Any]):
        """Save repository overview to separate storage (not in regular elements)"""
        repo_name = repo_overview.get("repo_name", "Unknown")
        summary = repo_overview.get("summary", "")
        structure_text = repo_overview.get("structure_text", "")
        readme_content = repo_overview.get("readme_content", "")
        
        # # Combine all textual information for embedding
        # overview_text = f"{summary}\n\n{structure_text}"
        # if readme_content:
        #     overview_text += f"\n\nREADME:\n{readme_content[:3000]}"  # Include truncated README

        # Combine all textual information for embedding
        overview_text = f"{summary}"
        if readme_content:
            overview_text += f"\n\nREADME:\n{readme_content[:2000]}"  # Include truncated README
        
        # Generate embedding for the overview
        embedding = self.embedder.embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT")
        
        # Prepare metadata
        metadata = {
            "summary": summary,
            "file_structure": repo_overview.get("file_structure", {}),
            "structure_text": structure_text,
            "readme_content": readme_content,
            "has_readme": repo_overview.get("has_readme", False),
            "repo_url": self.current_repo_url,
        }
        
        # Save to separate storage via vector_store
        if self.vector_store:
            self.vector_store.save_repo_overview(
                repo_name=repo_name or self.current_repo_name,
                overview_content=overview_text,
                embedding=embedding,
                metadata=metadata
            )
        else:
            self.logger.warning("Vector store not provided, repository overview not saved separately")
    
    def _extract_lines(self, content: str, start_line: int, end_line: int) -> str:
        """Extract lines from content"""
        lines = content.split("\n")
        # Convert to 0-indexed
        start = max(0, start_line - 1)
        end = min(len(lines), end_line)
        return "\n".join(lines[start:end])
    
    def _generate_file_summary(self, parse_result: FileParseResult) -> str:
        """Generate summary for a file"""
        parts = []
        
        if parse_result.module_docstring:
            # Use first line of docstring
            first_line = parse_result.module_docstring.split("\n")[0]
            parts.append(first_line)
        
        # Add class/function counts
        if parse_result.classes:
            parts.append(f"{len(parse_result.classes)} classes")
        if parse_result.functions:
            parts.append(f"{len(parse_result.functions)} functions")
        
        # Add language
        parts.append(f"{parse_result.language} file")
        
        return ", ".join(parts) if parts else f"{parse_result.language} source file"
    
    def _generate_id(self, type_: str, *parts: str) -> str:
        """
        Generate deterministic unique ID for code element using hashing.
        Format: {repo}_{type}_{hash(path+identifier)}
        """
        repo_prefix = normalize_path(self.current_repo_name) if self.current_repo_name else "default"
        unique_string = f"{repo_prefix}/{type_}/{'/'.join(str(p) for p in parts)}"

        hash_suffix = hashlib.md5(unique_string.encode("utf-8")).hexdigest()[:16]

        return f"{repo_prefix}_{type_}_{hash_suffix}"
    
    def get_elements_by_type(self, element_type: str) -> List[CodeElement]:
        """Get all elements of a specific type"""
        return [elem for elem in self.elements if elem.type == element_type]
    
    def get_elements_by_file(self, file_path: str) -> List[CodeElement]:
        """Get all elements from a specific file"""
        return [elem for elem in self.elements if elem.file_path == file_path]
    
    def get_element_by_id(self, element_id: str) -> Optional[CodeElement]:
        """Get element by ID"""
        for elem in self.elements:
            if elem.id == element_id:
                return elem
        return None
    
    def get_repository_overview(self) -> Optional[Dict[str, Any]]:
        """
        Get repository overview from separate storage
        Note: Repository overviews are no longer stored in self.elements
        """
        if self.vector_store and self.current_repo_name:
            overviews = self.vector_store.load_repo_overviews()
            return overviews.get(self.current_repo_name)
        return None


def index_repo(
    repo_path: str,
    db_path: str,
    max_file_size_bytes: int = 1_000_000,
) -> Dict[str, int]:
    """
    Walk repo_path and write all parsed code chunks into the SQLite database at
    db_path. Change detection is performed via mtime_ns and SHA-256 content hash.

    Args:
        repo_path: Absolute path to the repository root.
        db_path: Filesystem path to the SQLite database file.
        max_file_size_bytes: Files larger than this are silently skipped.

    Returns:
        Dict with keys: indexed, skipped, deleted, errors (all int counts).
    """
    conn = init_db(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    indexed = 0
    skipped = 0
    deleted = 0
    errors = 0

    # Load .gitignore patterns
    gitignore_path = os.path.join(repo_path, ".gitignore")
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8", errors="replace") as fh:
            spec = pathspec.PathSpec.from_lines("gitignore", fh)
    else:
        spec = pathspec.PathSpec.from_lines("gitignore", [])

    seen_paths: set = set()

    for dirpath, dirs, files in os.walk(repo_path, topdown=True):
        # Prune hidden directories in-place
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in files:
            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, repo_path)

            # .gitignore filtering
            if spec.match_file(rel_path):
                continue

            # Size filtering
            try:
                file_size = os.path.getsize(abs_path)
            except OSError:
                continue
            if file_size > max_file_size_bytes:
                continue

            try:
                stat_result = os.stat(abs_path)
                file_mtime_ns = stat_result.st_mtime_ns
                file_size = stat_result.st_size

                # Fast-path: check stored mtime_ns
                row = conn.execute(
                    "SELECT mtime_ns, content_hash FROM sources WHERE path = ?",
                    (rel_path,),
                ).fetchone()

                if row and row[0] == file_mtime_ns:
                    # mtime identical — assume unchanged
                    logger.info("Skipped %s (unchanged)", rel_path)
                    seen_paths.add(rel_path)
                    skipped += 1
                    continue

                # Read file bytes and compute hash
                with open(abs_path, "rb") as fh:
                    file_bytes = fh.read()
                file_hash = hashlib.sha256(file_bytes).hexdigest()

                if row and file_hash == row[1]:
                    # Content unchanged — only mtime drifted; update mtime
                    with conn:
                        conn.execute(
                            "UPDATE sources SET mtime_ns = ? WHERE path = ?",
                            (file_mtime_ns, rel_path),
                        )
                    logger.info("Skipped %s (unchanged)", rel_path)
                    seen_paths.add(rel_path)
                    skipped += 1
                    continue

                # File is new or changed — parse and index
                content = file_bytes.decode("utf-8", errors="replace")
                parse_result = CodeParser({}).parse_file(abs_path, content)
                if parse_result is None or parse_result.language == "unknown":
                    # Unsupported extension — skip silently
                    continue

                lines = content.split("\n")

                # Build chunk list: classes first, then functions
                raw_chunks = []
                for cls in parse_result.classes:
                    chunk_lines = lines[cls.start_line - 1 : cls.end_line]
                    raw_chunks.append((cls.start_line, cls.end_line, "\n".join(chunk_lines)))
                for func in parse_result.functions:
                    chunk_lines = lines[func.start_line - 1 : func.end_line]
                    raw_chunks.append((func.start_line, func.end_line, "\n".join(chunk_lines)))

                # Deduplicate by start_line (first occurrence wins)
                seen_starts: dict = {}
                for start, end, text in raw_chunks:
                    if start not in seen_starts:
                        seen_starts[start] = (start, end, text)
                chunks = list(seen_starts.values())

                # Fallback: treat entire file as one chunk if no classes/functions
                if not chunks:
                    chunks = [(1, len(lines), content)]

                with conn:
                    # Delete old data for this path (cascades to chunks)
                    conn.execute("DELETE FROM sources WHERE path = ?", (rel_path,))
                    # Insert new source record
                    conn.execute(
                        "INSERT INTO sources (path, content_hash, mtime_ns, size) "
                        "VALUES (?, ?, ?, ?)",
                        (rel_path, file_hash, file_mtime_ns, file_size),
                    )
                    # Insert chunks
                    for chunk_index, (start, end, text) in enumerate(chunks):
                        chunk_hash = hashlib.sha256(
                            text.encode("utf-8", errors="replace")
                        ).hexdigest()
                        conn.execute(
                            "INSERT INTO chunks "
                            "(source_path, content, content_hash, chunk_index, start_offset, end_offset) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (rel_path, text, chunk_hash, chunk_index, start, end),
                        )

                logger.info("Indexed %s", rel_path)
                seen_paths.add(rel_path)
                indexed += 1

            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to index %s: %s", rel_path, exc)
                errors += 1

    # Remove sources for files no longer on disk
    all_stored = [
        row[0] for row in conn.execute("SELECT path FROM sources").fetchall()
    ]
    for stored_path in all_stored:
        if stored_path not in seen_paths:
            with conn:
                conn.execute("DELETE FROM sources WHERE path = ?", (stored_path,))
            logger.info("Deleted %s (removed from disk)", stored_path)
            deleted += 1

    return {"indexed": indexed, "skipped": skipped, "deleted": deleted, "errors": errors}

