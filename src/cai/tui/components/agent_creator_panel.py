"""
Agent creator panel for building new agents with interactive UI
"""

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Static, Label, ListItem, ListView, Input, TextArea, Switch
from rich.markdown import Markdown
from rich.panel import Panel
import json
import os
from typing import Dict, List, Any, Optional
from cai.agents.agent_builder import AgentBuilder
from cai.sdk.agents.models.chatcompletions.litellm_adapter import acompletion_with_timeout


class AgentCreationConfirmed(Message):
    """Message sent when agent creation is confirmed"""
    def __init__(self, agent_config: Dict[str, Any]) -> None:
        super().__init__()
        self.agent_config = agent_config


class AgentCreationCancelled(Message):
    """Message sent when agent creation is cancelled"""
    pass


class AgentCreatorPanel(Container):
    """Interactive panel for creating new agents with system prompts and tools"""
    
    DEFAULT_CSS = """
    AgentCreatorPanel {
        layer: overlay;
        width: 100%;
        height: 100%;
        display: none;
    }
    
    AgentCreatorPanel.visible {
        display: block;
    }
    
    /* Dark overlay with blur effect */
    #agent-creator-overlay {
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.85);
        align: center middle;
    }
    
    /* Main container - modern card design */
    #agent-creator-content {
        width: 80%;
        max-width: 100;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: tall $primary;
        overflow: hidden;
    }
    
    /* Header with clean design */
    #creator-header {
        height: 4;
        padding: 1 2;
        background: $primary;
        color: $background;
        text-align: center;
        text-style: bold;
        dock: top;
        border-bottom: solid $primary-lighten-2;
    }
    
    /* Scrollable content area */
    #creator-body-scroll {
        height: 100%;
        scrollbar-background: #2e4f46;
        scrollbar-color: #529d86;
        scrollbar-size: 1 1;
    }
    
    /* Content area with proper spacing */
    #creator-body {
        height: auto;
        padding: 2 3;
    }
    
    /* Form sections with modern styling */
    .form-section {
        margin: 0 0 2 0;
        padding: 2;
        background: $background;
        border: solid $surface-lighten-2;
    }
    
    .form-section:focus-within {
        border: solid $primary;
        background: $background-lighten-1;
    }
    
    .form-label {
        margin: 0 0 1 0;
        color: $primary;
        text-style: bold;
        height: 1;
    }
    
    .hint-text {
        margin: 0 0 1 0;
        color: $text-muted;
        text-style: italic;
        height: auto;
    }
    
    /* TextArea with proper multiline display */
    #agent-description {
        width: 100%;
        height: 12;
        min-height: 10;
        padding: 1;
        border: solid $surface-lighten-3;
        background: $background-darken-1;
    }
    
    #agent-description:focus {
        border: solid $primary;
        background: $background;
    }
    
    
    /* ListView for tools with improved styling */
    #tools-list {
        height: 10;
        margin: 0;
        border: solid $surface-lighten-3;
        background: $background-darken-1;
        scrollbar-size: 1 1;
        scrollbar-color: #529d86;
        scrollbar-background: #2e4f46;
    }
    
    #tools-list > ListItem {
        padding: 1 2;
        height: 2;
        border-bottom: solid $surface-lighten-1;
    }
    
    #tools-list > ListItem:last-of-type {
        border-bottom: none;
    }
    
    #tools-list > ListItem.selected {
        background: $primary-darken-3;
        text-style: bold;
    }
    
    #tools-list > ListItem:hover {
        background: $surface-lighten-1;
    }
    
    #tools-list Label {
        width: 100%;
        content-align: left middle;
    }
    
    /* Status message with better visibility */
    #status-message {
        height: auto;
        min-height: 3;
        padding: 1 2;
        margin: 0;
        text-align: center;
        background: $surface-lighten-1;
        border: solid $surface-lighten-3;
    }
    
    /* Button bar with modern styling */
    #creator-buttons {
        height: 6;
        padding: 2;
        align: center middle;
        background: $surface-darken-1;
        dock: bottom;
        border-top: solid $surface-lighten-2;
    }
    
    #creator-buttons Button {
        margin: 0 2;
        width: 20;
        height: 3;
    }
    
    /* Button hover effects */
    #btn-create:hover {
        background: $success-lighten-1;
    }
    
    #btn-cancel:hover {
        background: $error-lighten-1;
    }
    """

    BINDINGS = [
        Binding("ctrl+g", "generate", "Generate Config"),
        Binding("ctrl+s", "save", "Save Agent"),
        Binding("escape", "cancel", "Cancel"),
    ]

    visible = reactive(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Pre-select generic_linux_command
        self.selected_tools = {"generic_linux_command"}
        self.agent_config = {
            "name": "",
            "description": "",
            "system_prompt": "",
            "tools": [],
            "model": "default",
            "temperature": 0.7
        }
        # Ensure panel starts hidden
        self.display = False

    def compose(self) -> ComposeResult:
        """Compose the panel UI"""
        with Container(id="agent-creator-overlay"):
            with Vertical(id="agent-creator-content"):
                # Header
                yield Static("🤖 Create New Agent", id="creator-header")
                
                # Scrollable body
                with ScrollableContainer(id="creator-body-scroll"):
                    with Container(id="creator-body"):
                        # Description section - User only enters what they want
                        with Vertical(classes="form-section"):
                            yield Label("Describe what you want your agent to do:", classes="form-label")
                            yield Static("Write in any language. I'll create everything for you.", classes="hint-text")
                            yield TextArea(id="agent-description")
                        
                        # Tool selection section
                        with Vertical(id="tools-section", classes="form-section"):
                            yield Label("Select tools for your agent:", classes="form-label")
                            yield Static("Click to toggle selection", classes="hint-text")
                            yield ListView(
            ListItem(Label("☑ generic_linux_command - Execute commands"), name="generic_linux_command"),
                                ListItem(Label("□ execute_code - Execute Python/other code"), name="execute_code"),
                                ListItem(Label("□ shodan_search - Search Shodan for hosts"), name="shodan_search"),
                                ListItem(Label("□ shodan_host_info - Get Shodan host details"), name="shodan_host_info"),
                                ListItem(Label("□ make_web_search_with_explanation - AI-powered web search"), name="make_web_search_with_explanation"),
                                id="tools-list"
                            )
                        
                        # Status messages
                        yield Static("", id="status-message")
                
                # Button bar (outside scrollable area)
                with Horizontal(id="creator-buttons"):
                    yield Button("Create Agent", id="btn-create", variant="success")
                    yield Button("Cancel", id="btn-cancel", variant="error")

    def on_mount(self) -> None:
        """Initialize the panel when mounted"""
        self.generated_config = None
        
        # Set up TextArea to be more accessible
        desc_area = self.query_one("#agent-description", TextArea)
        desc_area.can_focus = True

    async def _generate_agent_config(self, description: str) -> Dict[str, Any]:
        """Generate agent configuration from description using AI"""
        # This would call an AI model to generate the configuration
        # For now, we'll create a simple implementation
        
        # Extract key information from description
        description_lower = description.lower()
        
        # Determine agent type
        if any(word in description_lower for word in ['security', 'pentesting', 'vulnerability', 'exploit', 'hack']):
            agent_type = "security"
            specialization = "Security Testing and Vulnerability Assessment"
        elif any(word in description_lower for word in ['develop', 'code', 'program', 'build', 'create']):
            agent_type = "development"
            specialization = "Software Development and Code Generation"
        elif any(word in description_lower for word in ['research', 'analyze', 'investigate', 'study']):
            agent_type = "research"
            specialization = "Research and Analysis"
        else:
            agent_type = "security"  # Default
            specialization = "General Purpose Security Agent"
        
        # Generate agent name from description
        words = description.split()[:3]
        agent_name = "_".join(word.lower() for word in words if word.isalnum())[:20] + "_agent"
        
        # Generate system prompt in English
        system_prompt = AgentBuilder.generate_complex_prompt(agent_type, specialization)
        
        # Auto-suggest tools based on description
        suggested_tools = []
        if 'web' in description_lower or 'internet' in description_lower:
            suggested_tools.extend(['web_search', 'web_crawler'])
        if 'scan' in description_lower or 'network' in description_lower:
            suggested_tools.extend(['nmap_scanner', 'subdomain_enum'])
        if 'code' in description_lower or 'execute' in description_lower:
            suggested_tools.append('execute_code')
        if 'exploit' in description_lower or 'vulnerability' in description_lower:
            suggested_tools.extend(['metasploit', 'exploit_db'])
        
        # Always include basic tool
        if 'generic_linux_command' not in suggested_tools:
            suggested_tools.insert(0, 'generic_linux_command')
        
        return {
            "name": agent_name,
            "description": f"Agent specialized in: {description}",
            "system_prompt": system_prompt,
            "suggested_tools": suggested_tools,
            "temperature": 0.7
        }

    def show(self) -> None:
        """Show the agent creator panel"""
        self.visible = True
        self.display = True
        self.add_class("visible")
        
        # Clear previous content
        desc_area = self.query_one("#agent-description", TextArea)
        desc_area.clear()
        status_msg = self.query_one("#status-message", Static)
        status_msg.update("")
        
        # Reset state but keep generic_linux_command selected
        self.generated_config = None
        self.selected_tools = {"generic_linux_command"}
        
        # Focus on description area after a brief delay
        self.set_timer(0.1, lambda: desc_area.focus())

    def hide(self) -> None:
        """Hide the panel"""
        self.visible = False
        self.display = False
        self.remove_class("visible")


    async def action_generate(self) -> None:
        """Generate agent configuration"""
        await self._handle_generate()
    
    def action_save(self) -> None:
        """Save the agent configuration"""
        self._create_agent()

    def action_cancel(self) -> None:
        """Cancel agent creation"""
        self.post_message(AgentCreationCancelled())
        self.hide()

    def _create_agent(self) -> None:
        """Create the agent with current configuration"""
        if not self.generated_config:
            config_preview = self.query_one("#config-preview", Static)
            config_preview.update("[red]Please generate configuration first![/red]")
            return
        
        # Build final agent configuration with selected tools
        self.agent_config = {
            "name": self.generated_config["name"],
            "description": self.generated_config["description"],
            "system_prompt": self.generated_config["system_prompt"],
            "tools": list(self.selected_tools),
            "model": "default",
            "temperature": self.generated_config.get("temperature", 0.7)
        }
        
        # Send confirmation message
        self.post_message(AgentCreationConfirmed(self.agent_config))
        self.hide()

    @on(Button.Pressed)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        if button_id == "btn-create":
            await self._handle_create()
        elif button_id == "btn-cancel":
            self.action_cancel()
        event.stop()
    
    async def _handle_create(self) -> None:
        """Handle the create button click using meta agent"""
        desc_area = self.query_one("#agent-description", TextArea)
        description = desc_area.text.strip()
        
        if not description:
            status_msg = self.query_one("#status-message", Static)
            status_msg.update("[red]Please enter a description first![/red]")
            return
        
        # Get selected tools
        if not self.selected_tools:
            status_msg = self.query_one("#status-message", Static)
            status_msg.update("[red]Please select at least one tool![/red]")
            return
        
        # Update status
        status_msg = self.query_one("#status-message", Static)
        status_msg.update("[yellow]🤖 Creating your agent...[/yellow]")
        
        try:
            # Use meta agent to generate complete configuration
            config = await self._use_meta_agent_for_creation(description, list(self.selected_tools))
            
            if config:
                # Build and save the agent file
                agent_file_content = AgentBuilder.build_agent_file(config)
                
                # Ensure personal directory exists
                personal_dir = "/Users/luijait/cai_gitlab/src/cai/agents/personal"
                os.makedirs(personal_dir, exist_ok=True)
                
                # Save the agent file
                agent_filename = f"{config['name']}.py"
                agent_path = os.path.join(personal_dir, agent_filename)
                
                with open(agent_path, 'w') as f:
                    f.write(agent_file_content)
                
                # Update status with success
                status_msg.update(f"[green]✅ Agent '{config['name']}' created successfully![/green]")
                
                # Refresh the agent list in the sidebar
                try:
                    from cai.tui.components.sidebar import Sidebar
                    sidebar = self.app.query_one("#sidebar", Sidebar)
                    sidebar.refresh_agents()
                except Exception:
                    pass  # Sidebar might not exist in some contexts
                
                # Post success message and close after delay
                self.set_timer(2.0, self.hide)
            else:
                status_msg.update("[red]❌ Failed to generate agent configuration[/red]")
        
        except Exception as e:
            status_msg.update(f"[red]❌ Error: {str(e)}[/red]")
    
    # This method is no longer needed since we're not pre-generating configs

    @on(ListView.Selected)
    def on_tool_selected(self, event: ListView.Selected) -> None:
        """Handle tool selection"""
        if event.item and isinstance(event.item, ListItem):
            # Skip category headers
            if not hasattr(event.item, 'name') or not event.item.name:
                return
                
            tool_id = event.item.name
            label = event.item.query_one(Label)
            current_text = str(label.renderable)
            
            if tool_id in self.selected_tools:
                # Deselect
                self.selected_tools.remove(tool_id)
                event.item.remove_class("selected")
                new_text = current_text.replace("☑", "□")
            else:
                # Select
                self.selected_tools.add(tool_id)
                event.item.add_class("selected")
                new_text = current_text.replace("□", "☑")
            
            label.update(new_text)
        event.stop()
    
    async def _use_meta_agent_for_creation(self, description: str, selected_tools: List[str]) -> Optional[Dict[str, Any]]:
        """Use a meta agent to generate complete agent configuration"""
        try:
            # Meta agent prompt to create comprehensive agent configuration
            meta_prompt = f"""You are an expert AI agent creator. Based on the following description, create a complete agent configuration.

User Description: {description}

Selected Tools by User: {', '.join(selected_tools)}

Generate a complete agent configuration that includes:
1. A descriptive agent name (snake_case, ending with _agent)
2. A comprehensive description of the agent's purpose
3. A detailed, well-structured system prompt in English that:
   - Clearly defines the agent's role and expertise
   - Lists specific capabilities and responsibilities
   - Includes behavioral guidelines
   - Is at least 500 words long
   - Mentions how to use the selected tools effectively

Return ONLY a JSON object with this exact structure:
{{
    "name": "example_agent",
    "description": "Agent specialized in...",
    "system_prompt": "You are an expert...",
    "tools": {selected_tools},
    "temperature": 0.7
}}

IMPORTANT: The "tools" field in your response must be exactly: {json.dumps(selected_tools)}
"""

            # Use litellm to generate the configuration
            model_name = os.getenv("CAI_MODEL", "gpt-4")
            kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are an AI agent configuration generator. Always respond with valid JSON only."},
                    {"role": "user", "content": meta_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            }
            response = await acompletion_with_timeout(
                kwargs, stream=False, model_name=model_name
            )
            
            # Parse the response
            content = response.choices[0].message.content.strip()
            
            # Clean up the response if needed
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            config = json.loads(content.strip())
            
            # Validate required fields
            required_fields = ["name", "description", "system_prompt", "tools"]
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required field: {field}")
            
            # Ensure tools is a list
            if not isinstance(config["tools"], list):
                config["tools"] = [config["tools"]]
            
            # Always include generic_linux_command
            if "generic_linux_command" not in config["tools"]:
                config["tools"].insert(0, "generic_linux_command")
            
            return config
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {e}")
            return None
        except Exception as e:
            print(f"Error generating agent configuration: {e}")
            return None

