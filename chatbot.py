import streamlit as st
import requests
import json
from PIL import Image
import pytesseract

# ---------------- Tesseract Path ----------------
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# ---------------- Session State ----------------
st.session_state.setdefault("chats", {})
st.session_state.setdefault("current_chat", None)
st.session_state.setdefault("chat_counter", 0)
st.session_state.setdefault("extracted_text", "")
st.session_state.setdefault("titles", {})
st.session_state.setdefault("input_box", "")
st.session_state.setdefault("instruction_box", "")
st.session_state.setdefault("uploaded_image", None)
st.session_state.setdefault("uploader_key", "file_uploader_0")
st.session_state.setdefault("chat_images", {})  # store uploaded image per chat
st.session_state.setdefault("ocr_done", False)  # prevents double OCR

# ---------------- Ollama Backend ----------------
def bot_reply(user_msg):
    try:
        history = ""
        if st.session_state.current_chat:
            for sender, text in st.session_state.chats[st.session_state.current_chat]:
                prefix = "User: " if sender == "user" else "Assistant: "
                history += prefix + text + "\n"

        prompt = history + f"User: {user_msg}\nAssistant:"
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama2", "prompt": prompt},
            stream=True,
        )

        full_reply = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                if "response" in data:
                    full_reply += data["response"]
                if data.get("done", False):
                    break
        return full_reply.strip() if full_reply else "Sorry, I couldn’t generate a reply."
    except Exception as e:
        return f"❌ Backend error: {e}"

# ---------------- Sidebar ----------------
st.sidebar.title("💭 Conversations")

# ---- New Chat ----
if st.sidebar.button("➕ Start New Chat"):
    st.session_state.chat_counter += 1
    new_chat_key = f"chat_{st.session_state.chat_counter}"
    st.session_state.chats[new_chat_key] = []
    st.session_state.current_chat = new_chat_key
    st.session_state.titles[new_chat_key] = f"Chat {st.session_state.chat_counter}"

    # Reset per-chat data
    st.session_state.extracted_text = ""
    st.session_state.instruction_box = ""
    st.session_state.uploaded_image = None
    st.session_state.chat_images[new_chat_key] = None
    st.session_state.uploader_key = f"file_uploader_{st.session_state.chat_counter}"
    st.session_state.ocr_done = False
    st.rerun()

# ---- Chat Selector ----
if st.session_state.chats:
    chat_display_names = [
        st.session_state.titles.get(key, f"Chat {i+1}")
        for i, key in enumerate(st.session_state.chats.keys())
    ]
    selected_chat = st.sidebar.radio(
        "Select Chat",
        chat_display_names,
        index=list(st.session_state.chats.keys()).index(st.session_state.current_chat)
        if st.session_state.current_chat else 0,
    )
    for key, title in st.session_state.titles.items():
        if title == selected_chat:
            st.session_state.current_chat = key
            break

# ---------------- Main Area ----------------
st.title("ChatGPT Clone with OCR Integration")

# ---- OCR Upload & Preview ----
st.subheader("📸 Upload Image for OCR Extraction")

uploaded_file = st.file_uploader(
    "Upload an image (JPG, PNG, JPEG)",
    type=["jpg", "jpeg", "png"],
    key=st.session_state.uploader_key
)

# Auto OCR extraction only once per new image
if uploaded_file:
    if st.session_state.uploaded_image != uploaded_file or not st.session_state.ocr_done:
        st.session_state.uploaded_image = uploaded_file
        st.session_state.chat_images[st.session_state.current_chat] = uploaded_file
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_container_width=True)

        # Auto extract text
        try:
            with st.spinner("Extracting text..."):
                st.session_state.extracted_text = pytesseract.image_to_string(image).strip()
            st.session_state.ocr_done = True
            if st.session_state.extracted_text:
                st.success("✅ Text extracted successfully!")
            else:
                st.warning("⚠️ No readable text found.")
        except Exception as e:
            st.error(f"Error during OCR: {e}")
    else:
        st.image(Image.open(uploaded_file), caption="Uploaded Image", use_container_width=True)
else:
    # Show previous image for current chat if available
    current_chat = st.session_state.current_chat
    if current_chat and st.session_state.chat_images.get(current_chat):
        st.image(
            Image.open(st.session_state.chat_images[current_chat]),
            caption="Previously Uploaded Image",
            use_container_width=True,
        )

# ---- OCR Text Display ----
if st.session_state.extracted_text:
    st.text_area("🧾 Extracted Text (Preview)", st.session_state.extracted_text, height=150)

# ---- Send OCR + Instruction ----
def send_ocr_to_chat():
    extracted_text = st.session_state.extracted_text.strip()
    instruction = st.session_state.instruction_box.strip()

    if not extracted_text:
        st.warning("⚠️ No extracted text to send!")
        return

    if not st.session_state.current_chat:
        st.session_state.chat_counter += 1
        new_chat_key = f"chat_{st.session_state.chat_counter}"
        st.session_state.chats[new_chat_key] = []
        st.session_state.current_chat = new_chat_key
        st.session_state.titles[new_chat_key] = "OCR Chat"

    combined_prompt = f"{instruction}\n\n{extracted_text}" if instruction else extracted_text

    st.session_state.chats[st.session_state.current_chat].append(("user", combined_prompt))
    reply = bot_reply(combined_prompt)
    st.session_state.chats[st.session_state.current_chat].append(("bot", reply))

    # Update chat title
    if len(st.session_state.chats[st.session_state.current_chat]) <= 2:
        short_title = instruction[:50] if instruction else extracted_text.split("\n")[0][:50]
        st.session_state.titles[st.session_state.current_chat] = short_title + "..."

    st.session_state.extracted_text = ""
    st.session_state.instruction_box = ""
    st.session_state.ocr_done = False

st.text_input(
    "💭 Ask something about the extracted text:",
    placeholder="Summarize, explain, or translate...",
    key="instruction_box",
)
st.button("🚀 Send to Chat", on_click=send_ocr_to_chat)

# ---- Display Chat ----
st.subheader("💬 Conversation")
if st.session_state.current_chat:
    for sender, message in st.session_state.chats[st.session_state.current_chat]:
        align = "flex-end" if sender == "user" else "flex-start"
        bg_color = "#DCF7C5" if sender == "user" else "#F3F3F3"
        st.markdown(
            f"""
            <div style="display:flex; justify-content:{align}; margin:6px;">
                <div style="background-color:{bg_color}; padding:12px; border-radius:16px; 
                            max-width:70%; word-wrap:break-word; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
                    {message}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        "<h4 style='color:gray;'>Start a new chat or upload an image to begin!</h4>",
        unsafe_allow_html=True,
    )

# ---- Normal Chat Input ----
def send_message():
    new_msg = st.session_state.input_box.strip()
    if new_msg:
        if not st.session_state.current_chat:
            st.session_state.chat_counter += 1
            new_chat_key = f"chat_{st.session_state.chat_counter}"
            st.session_state.chats[new_chat_key] = []
            st.session_state.current_chat = new_chat_key
            st.session_state.titles[new_chat_key] = "New Chat"

        st.session_state.chats[st.session_state.current_chat].append(("user", new_msg))
        reply = bot_reply(new_msg)
        st.session_state.chats[st.session_state.current_chat].append(("bot", reply))

        if len(st.session_state.chats[st.session_state.current_chat]) == 2:
            st.session_state.titles[st.session_state.current_chat] = new_msg[:50] + "..."

        st.session_state.input_box = ""

st.text_input("Type your message...", key="input_box", on_change=send_message)

# ---- Footer ----
st.markdown(
    "<div style='text-align:center; color:gray; font-size:12px; margin-top:40px;'>"
    "✨ Built with ❤️ by Sri Nithya ✨</div>",
    unsafe_allow_html=True,
)
