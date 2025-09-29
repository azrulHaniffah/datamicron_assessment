import gradio as gr
import google.generativeai as genai
import os
from typing import List, Tuple, Dict, Any
import json
from search_router import get_answer

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class GeminiChatbot:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash-001')
        self.chat_history = []
        
    def format_search_results(self, search_data: Dict[str, Any]) -> str:
        """Format search results into a readable context for the LLM"""
        if not search_data or not search_data.get("results"):
            return "No relevant information found."
        
        context = f"Search source: {search_data['source']}\n\n"
        context += "Relevant information found:\n"
        
        for i, result in enumerate(search_data["results"], 1):
            title = result.get("title", "No title")
            text = result.get("article_content", "No content")
            url = result.get("url", "")
            internal_id = result.get("news_id", "")
            score = result.get("score", 0)
            
            context += f"\n{i}. **{title}**\n"
            if score:
                context += f"   Relevance: {score:.2f}\n"
            context += f"   Content: {text[:5000]}{'...' if len(text) > 500 else ''}\n"

            if internal_id != "":
                if url:
                    context += f"   Source: {url}\n"
                    context += f"   Source internal_id: {internal_id}\n"
            else :
                context += f"   Source: {url}\n"

        return context
    
    def create_prompt(self, user_query: str, search_context: str) -> str:
       
        prompt = f"""You are a helpful AI assistant that provides accurate and informative responses based on search results and your knowledge.

User Question: {user_query}

Search Context:
{search_context}

Instructions:
1. Justify the search source is from internal or web.
2. Use the search context to provide accurate, relevant information
3. If the search context doesn't contain sufficient information, use your general knowledge but clearly indicate this
4. Provide a well-structured, comprehensive response
5. Include relevant details and examples when helpful
6. If applicable, mention the sources of information
7. Be conversational and helpful in tone
8. If the search results are not relevant to the question, say so and provide what help you can from your knowledge.

Please provide a helpful response:"""
        
        return prompt
    
    def chat(self, message: str, history: List[Tuple[str, str]]) -> Tuple[str, List[Tuple[str, str]]]:

        try:
       
            search_data = get_answer(message, k=3, max_chars=8000)
            search_context = self.format_search_results(search_data)
            
            prompt = self.create_prompt(message, search_context)
 
            response = self.model.generate_content(prompt)
            ai_response = response.text
            
            sources = []
            for result in search_data.get("results", []):
                url = result.get("url")
                news_id = result.get("news_id")
                if url and news_id != "":
                    sources.append(url + f" (Internal ID: {news_id})")
                else:
                    sources.append(url)

            if sources:
                ai_response += "\n\n**Sources:**\n" + "\n".join(f"- {s}" for s in sources)

            history.append((message, ai_response))
            
            return "", history
            
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            history.append((message, error_msg))
            return "", history
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_history = []
        return [], []

def create_gradio_interface():
    """Create and configure the Gradio interface"""
    chatbot = GeminiChatbot()
    
    with gr.Blocks(
        theme=gr.themes.Soft(),
        title="Smart Search Chatbot",
        css="""
        .gradio-container {
            max-width: 1000px;
            margin: auto;
        }
        .chat-container {
            height: 600px;
        }
        """
    ) as demo:
        
        gr.Markdown(
            """
            # 🤖 Smart Search Chatbot
            
            Ask me anything! I'll search for relevant information and provide comprehensive answers using Gemini AI.
            
            **Features:**
            - 🔍 Intelligent search across internal knowledge and web
            - 🧠 AI-powered responses using Google's Gemini
            - 📚 Context-aware answers with source attribution
            - 💬 Natural conversation flow
            """
        )
        
        chatbot_interface = gr.Chatbot(
            label="Chat History",
            height=500,
            container=True,
            bubble_full_width=False,
            show_copy_button=True
        )
        
        with gr.Row():
            msg_input = gr.Textbox(
                label="Your Message",
                placeholder="Ask me anything...",
                lines=2,
                scale=4
            )
            
            with gr.Column(scale=1):
                submit_btn = gr.Button("Send", variant="primary", size="lg")
                clear_btn = gr.Button("Clear Chat", variant="secondary")

        def respond(message, history):
            return chatbot.chat(message, history)

        submit_btn.click(
            respond,
            inputs=[msg_input, chatbot_interface],
            outputs=[msg_input, chatbot_interface]
        )
        
        msg_input.submit(
            respond,
            inputs=[msg_input, chatbot_interface],
            outputs=[msg_input, chatbot_interface]
        )
        
        clear_btn.click(
            chatbot.clear_chat,
            outputs=[chatbot_interface, msg_input]
        )
        
        gr.Markdown(
            """
            ### How it works:
            1. **Search**: Your question is searched across internal knowledge base and web sources
            2. **Rank**: Results are ranked by relevance to your query
            3. **Generate**: Gemini AI synthesizes the information into a comprehensive response
            4. **Respond**: You get an intelligent, context-aware answer with source information
            
            💡 **Tip**: Be specific in your questions for better results!
            """
        )
    
    return demo

def main():

    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  Warning: GEMINI_API_KEY environment variable not set!")
        print("Please set your Gemini API key:")
        print("export GEMINI_API_KEY='your-api-key-here'")
        return
    
    print("🚀 Starting Smart Search Chatbot...")
    print("📡 Checking Gemini API connection...")
    
    try:
        # Test API connection
        model = genai.GenerativeModel('gemini-2.0-flash-001')
        test_response = model.generate_content("Hello")
        print("✅ Gemini API connected successfully!")
    except Exception as e:
        print(f"❌ Failed to connect to Gemini API: {e}")
        return
    
    demo = create_gradio_interface()
    
    print("🌐 Launching Gradio interface...")
    demo.launch(
        server_name="0.0.0.0",
        server_port=8080,
        share=True,  # Set to True if you want a public link
        debug=True
    )

if __name__ == "__main__":
    main()