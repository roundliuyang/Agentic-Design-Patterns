# %%
import os
import sys
import asyncio
import uuid

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams
from google.genai.types import Content, Part
from mcp import StdioServerParameters

# Create a reliable absolute path to a folder named 'mcp_managed_files'
# within the same directory as this agent script.
# This ensures the agent works out-of-the-box for demonstration.
# For production, you would point this to a more persistent and secure location.
TARGET_FOLDER_PATH = os.path.join(os.getcwd(), "mcp_managed_files")

# Ensure the target directory exists before the agent needs it.
os.makedirs(TARGET_FOLDER_PATH, exist_ok=True)

root_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='filesystem_assistant_agent',
    instruction=(
        'Help the user manage their files. You can list files, read files, and write files. '
        f'You are operating in the following directory: {TARGET_FOLDER_PATH}'
    ),
    tools=[
        MCPToolset(
            connection_params=StdioServerParameters(
                command='npx',
                args=[
                    "-y",  # Argument for npx to auto-confirm install
                    "@modelcontextprotocol/server-filesystem",
                    # This MUST be an absolute path to a folder.
                    TARGET_FOLDER_PATH,
                ],
            ),
            # Optional: You can filter which tools from the MCP server are exposed.
            # For example, to only allow reading:
            # tool_filter=['list_directory', 'read_file']
        )
    ],
)

# 内容我们要写入 hello.txt
file_name = "hello.txt"
file_content = "Hello, this is a test file created by the agent!"

# 构建指令给 agent
instruction = f"Create a file named '{file_name}' and write the following content into it:\n{file_content}"

# 使用 InMemoryRunner 执行（ADK 1.8.0+ 的正确方式）
runner = InMemoryRunner(agent=root_agent)
user_id = "test_user"
session_id = f"test_session_{uuid.uuid4().hex[:8]}"


async def run_agent():
    # 必须先创建会话
    await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id
    )

    # 准备用户消息
    user_message = Content(parts=[Part(text=instruction)])

    # 调用 agent 执行操作
    response = None
    try:
        async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message
        ):
            if event.is_final_response():
                response = event.content.parts[0].text if event.content.parts else ""
                break
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 显式关闭 MCP 工具集以清理资源
        try:
            for tool in root_agent.tools:
                if hasattr(tool, 'close'):
                    await tool.close()
        except Exception as e:
            print(f"Warning during cleanup: {e}")

    return response


# 运行异步函数
response = asyncio.run(run_agent())

# 输出 agent 的反馈
if response:
    print(response)

# 验证文件是否创建成功
created_file_path = os.path.join(TARGET_FOLDER_PATH, file_name)
if os.path.exists(created_file_path):
    print(f"\n✓ File '{file_name}' successfully created at {created_file_path}")
    with open(created_file_path, 'r', encoding='utf-8') as f:
        print(f"  Content: {f.read()}")
else:
    print(f"\n✗ Failed to create file '{file_name}'")
