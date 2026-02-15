"""Prompt builder for wiki section generation with adaptive depth."""

from __future__ import annotations


class WikiPromptBuilder:
    """Builds prompts for LLM-based wiki content generation."""

    def build_what_explanation(
        self,
        *,
        name: str,
        description: str,
        topics: list[str] | None = None,
    ) -> str:
        """Build 'what' section deep dive content.
        
        Args:
            name: Project name.
            description: Project description.
            topics: Repository topics/tags.
            
        Returns:
            Markdown content for deep dive section.
        """
        topics_list = topics or []
        topics_text = ", ".join(topics_list[:5]) if topics_list else "general"

        return f"""## What is {name}?

{description}

### Purpose and Domain

{name} is a project focused on {topics_text}. It provides capabilities for developers working in this domain.

### Target Users

- **Engineers** looking to solve problems in {topics_text}
- **Teams** building applications requiring these capabilities
- **Learners** exploring this technical space

### Why This Project Matters

(Optional section - to be populated based on ecosystem context and community adoption patterns)
"""

    def build_how_explanation(
        self,
        *,
        name: str,
        description: str,
    ) -> str:
        """Build 'how' section explaining key concepts and workflow.
        
        Args:
            name: Project name.
            description: Project description.
            
        Returns:
            Markdown content for how it works.
        """
        return f"""## How {name} Works

### Key Concepts

{description}

### Workflow

1. **Setup**: Install and configure the project
2. **Usage**: Apply the core functionality to your use case
3. **Extension**: Customize and extend as needed

### Usage Patterns

This project provides developer-focused APIs and tooling for technical integration.

*(Full workflow details to be enhanced with README/docs analysis)*
"""

    def build_architecture_explanation(
        self,
        *,
        name: str,
        language: str,
    ) -> str:
        """Build architecture/codebase explanation with adaptive structure.
        
        Args:
            name: Project name.
            language: Primary programming language.
            
        Returns:
            Markdown content for architecture section.
        """
        return f"""## Architecture and Codebase

### Technical Stack

- **Primary Language**: {language}
- **Architecture**: *(To be inferred from repository structure)*

### Codebase Structure

The project follows standard {language} conventions with a modular design approach.

### Design Patterns

*(Adaptive explanation based on repository characteristics - to be enhanced with codebase analysis)*

### Component Overview

Main components and their responsibilities will be documented here based on repository analysis.
"""
