import streamlit as st
from google import genai
from google.genai import types
import json
import os

# --- 1. TETAPAN HALAMAN & KESELAMATAN (LOGIN) ---
st.set_page_config(page_title="AI Marketing Command Center", page_icon="⚡", layout="wide")

# Sistem kata laluan mudah agar orang luar tidak curi kuota Gemini anda
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Log Masuk AI Marketing Hub")
    pwd_input = st.text_input("Masukkan Kata Laluan Akses:", type="password")
    if st.button("Masuk"):
        if pwd_input == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Kata laluan salah!")
    st.stop()

# --- 2. SAMBUNGAN GEMINI CLIENT ---
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if not API_KEY:
    st.error("Ralat: Sila tetapkan GEMINI_API_KEY di Streamlit Secrets!")
    st.stop()

client = genai.Client(api_key=API_KEY)

# --- 3. MEMORI / PRODUCT KNOWLEDGE BASE LALAI ---
DEFAULT_KNOWLEDGE = {
    "Tone Wow": {
        "kategori": "Telco & Jana Pendapatan Pasif",
        "usp": "Simkad prabayar pelan data jimat yang membayar komisen berulang apabila pengguna topup.",
        "avatar": "Pengguna telefon yang ingin kurangkan bil bulanan & individu yang cari pendapatan sampingan.",
        "compliance": "Dilarang janjikan pendapatan goyang kaki atau guna perkataan skim cepat kaya."
    },
    "Eastel": {
        "kategori": "Telco Mampu Milik",
        "usp": "Penyedia pelan internet pantas dengan kuota besar pada harga marhaen.",
        "avatar": "Pelajar universiti, pekerja gig, dan keluarga bajet.",
        "compliance": "Fokus pada kestabilan liputan dan penjimatan wang."
    },
    "Produk AI": {
        "kategori": "Perisian & Automasi AI",
        "usp": "Membantu usahawan menjimatkan masa copywriting, grafik, dan khidmat pelanggan dengan ejen AI.",
        "avatar": "Pemilik bisnes SME, agensi pemasaran, dan freelancer.",
        "compliance": "Jangan overclaim bahawa AI 100% menggantikan manusia tanpa semakan fakta."
    },
    "BeliBeliOnline": {
        "kategori": "E-Commerce & Marketplace Tempatan",
        "usp": "Platform beli-belah lokal mesra usahawan PKS dengan caj komisen rendah dan sokongan komuniti.",
        "avatar": "Peniaga kecil IKS di Malaysia dan pembeli barangan tempatan.",
        "compliance": "Jangan burukkan platform lain; fokus pada sokongan ekonomi peniaga tempatan."
    }
}

# --- 4. ANTARAMUKA PENGGUNA (SIDEBAR & MEMORI) ---
st.sidebar.title("🎛️ Pengurusan Produk")
selected_product = st.sidebar.selectbox("Pilih Produk:", list(DEFAULT_KNOWLEDGE.keys()))

st.sidebar.markdown("---")
st.sidebar.subheader("📄 Kemas Kini Pengetahuan (PDF)")
uploaded_pdf = st.sidebar.file_uploader(f"Muat naik dokumen terkini ({selected_product})", type=["pdf"])

# Papar info sedia ada
product_info = DEFAULT_KNOWLEDGE[selected_product]
with st.sidebar.expander("Lihat Ringkasan Pengetahuan Produk"):
    st.write(f"**USP:** {product_info['usp']}")
    st.write(f"**Target:** {product_info['avatar']}")
    st.write(f"**Pantang Larang:** {product_info['compliance']}")

# --- 5. LOGIK MULTI-AGENT (ORCHESTRATOR -> RESEARCH -> CONTENT -> QA) ---
def run_pipeline(product_name, base_info, pdf_file, objective):
    pdf_attachment = None
    if pdf_file is not None:
        # Simpan fail sementara untuk dimuat naik ke Gemini
        temp_path = f"temp_{pdf_file.name}"
        with open(temp_path, "wb") as f:
            f.write(pdf_file.getbuffer())
        pdf_attachment = client.files.upload(file=temp_path)
        os.remove(temp_path)

    # Langkah 1: Research Agent
    with st.spinner("🔍 1. Research Agent sedang mengkaji sudut pasaran..."):
        research_contents = [
            f"Kaji produk {product_name} berasaskan maklumat asas ini: {json.dumps(base_info)}.",
            f"Objektif kempen daripada pengasas: {objective}."
        ]
        if pdf_attachment:
            research_contents.append(pdf_attachment)
        research_contents.append("Tugasan: Berikan Analisis Avatar, 3 Masalah Utama (Pain Points), dan 2 Sudut Pemasaran Paling Berkesan.")

        research_res = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=research_contents,
            config=types.GenerateContentConfig(
                system_instruction="Awak ialah Market Research Agent yang tajam menganalisis pasaran Malaysia."
            )
        )
        research_data = research_res.text

    # Langkah 2: Content Agent
    with st.spinner("✍️ 2. Content Agent sedang menulis salinan media sosial..."):
        content_prompt = f"""
        Produk: {product_name}
        Hasil Kajian Penyelidik:
        {research_data}
        
        Objektif: {objective}
        
        Tugasan: Tulis copywriting berikut dalam Bahasa Melayu:
        1. Facebook Post (Format storytelling santai + emosi + Call to Action).
        2. X / Twitter Thread (Ringkas, padat, 'hook' menarik).
        3. Cadangan Visual (Prompt gambar AI atau idea poster).
        """
        content_res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=content_prompt,
            config=types.GenerateContentConfig(
                system_instruction="Awak ialah Content Creator & Copywriter pakar dalam pasaran media sosial Malaysia."
            )
        )
        content_data = content_res.text

    # Langkah 3: QA & Compliance Agent
    with st.spinner("⚖️ 3. QA Agent sedang menyemak kualiti dan pantang larang..."):
        qa_prompt = f"""
        Peraturan Khas Produk: {base_info['compliance']}
        Salinan Iklan yang Dijana:
        {content_data}
        
        Tugasan: 
        1. Semak adakah terdapat overclaim, salah fakta, atau melanggar undang-undang etika.
        2. Berikan Skor Kualiti Keseluruhan (1 hingga 10).
        3. Berikan nasihat penambahbaikan ringkas jika ada.
        """
        qa_res = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=qa_prompt,
            config=types.GenerateContentConfig(
                system_instruction="Awak ialah QA & Compliance Officer yang tegas dan teliti."
            )
        )
        qa_data = qa_res.text

    return research_data, content_data, qa_data

# --- 6. ANTARAMUKA UTAMA ---
st.title(f"🚀 AI Marketing Team: {selected_product}")
st.write("Arahkan pasukan ejen AI anda untuk menjana kempen lengkap dari kajian hingga semakan kualiti.")

campaign_goal = st.text_area(
    "Apakah objektif atau fokus kempen kali ini?", 
    placeholder="Contoh: Fokus promosi gaji masuk minggu ini untuk peniaga kecil sertai platform tanpa yuran pendaftaran."
)

if st.button("Jana Kempen Lengkap ⚡", type="primary"):
    if not campaign_goal.strip():
        st.warning("Sila masukkan objektif kempen anda terlebih dahulu!")
    else:
        tab1, tab2, tab3 = st.tabs(["📝 Copywriting & Visual", "🔍 Laporan Research", "⚖️ Semakan QA"])
        
        research_out, content_out, qa_out = run_pipeline(
            selected_product, 
            product_info, 
            uploaded_pdf, 
            campaign_goal
        )
        
        with tab1:
            st.subheader("Draf Kandungan Media Sosial")
            st.markdown(content_out)
            
        with tab2:
            st.subheader("Hasil Kajian Pasaran & Avatar")
            st.markdown(research_out)
            
        with tab3:
            st.subheader("Laporan Semakan Kualiti & Pematuhan")
            st.markdown(qa_out)
