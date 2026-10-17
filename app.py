import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client
import json
import tempfile
import os
import time

# =========================================================
# 1. TETAPAN HALAMAN & KESELAMATAN (LOGIN)
# =========================================================
st.set_page_config(page_title="Pro Marketing Command Center", page_icon="⚡", layout="wide")

APP_PASSWORD = st.secrets.get("APP_PASSWORD", "admin123")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Log Masuk Marketing Agent Hub")
    pwd_input = st.text_input("Kata Laluan Keselamatan:", type="password")
    if st.button("Log Masuk 🚀"):
        if pwd_input == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Kata laluan salah! Sila cuba lagi.")
    st.stop()

# =========================================================
# 2. SAMBUNGAN GEMINI & SUPABASE
# =========================================================
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

if not GEMINI_KEY:
    st.error("Ralat: GEMINI_API_KEY tidak dijumpai di Streamlit Secrets!")
    st.stop()

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Ralat: Maklumat SUPABASE_URL atau SUPABASE_KEY belum diisi di Secrets!")
    st.stop()

client = genai.Client(api_key=GEMINI_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# MODEL AKTIF: Kuota percuma 500 sehari (RPD)
MODEL_NAME = "gemini-3.1-flash-lite"

# =========================================================
# 3. ENJIN PANGGILAN AI (DENGAN DEEP THINKING SYSTEM PROMPTS)
# =========================================================
def call_gemini(contents, system_instruction=None):
    config = types.GenerateContentConfig()
    if system_instruction:
        config.system_instruction = system_instruction

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=config
    )
    return response.text

# =========================================================
# 4. PENGKALAN DATA PRODUK ASAS (KNOWLEDGE BASE INDUK)
# =========================================================
DEFAULT_KNOWLEDGE = {
    "Tone Wow": {
        "kategori": "Telco & Komisen Rujukan",
        "usp": "Simkad prabayar pelan data jimat yang memberi insentif komisen tunai berulang setiap kali pengguna topup.",
        "avatar": "Pengguna telefon yang ingin kurangkan beban kos sara hidup & individu mencari pendapatan sampingan sah.",
        "compliance": "Dilarang janjikan pendapatan goyang kaki atau guna istilah skim cepat kaya / skim piramid."
    },
    "Eastel": {
        "kategori": "Telco Mampu Milik",
        "usp": "Penyedia pelan internet pantas dengan kuota besar pada kadar mampu milik mesra poket marhaen.",
        "avatar": "Pelajar universiti, penghantar makanan / gig workers, dan keluarga yang mengutamakan penjimatan.",
        "compliance": "Fokus pada kestabilan liputan dan penjimatan kos bulanan sebenar."
    },
    "Produk AI": {
        "kategori": "Automasi & Perisian AI",
        "usp": "Sistem ejen pintar untuk automasi copywriting, analisis data, dan sokongan pemasaran bisnes PKS.",
        "avatar": "Pemilik bisnes PKS, usahawan solo, dan pencipta kandungan digital yang kekurangan tenaga kerja.",
        "compliance": "Jangan overclaim bahawa AI menggantikan 100% manusia tanpa semakan fakta."
    },
    "BeliBeliOnline": {
        "kategori": "Marketplace E-Commerce Tempatan",
        "usp": "Platform e-dagang tempatan mesra peniaga kecil dengan kadar komisen adil dan sokongan komuniti usahawan.",
        "avatar": "Peniaga kecil IKS tempatan dan pembeli barangan buatan Malaysia.",
        "compliance": "Elakkan membuat perbandingan agresif atau memburukkan platform e-commerce lain."
    }
}

def get_saved_knowledge(product_name):
    try:
        res = supabase.table("product_knowledge").select("*").eq("product_name", product_name).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
    except Exception as e:
        st.sidebar.error(f"Ralat capaian pangkalan data: {e}")
    return None

# =========================================================
# 5. INISIALISASI SESI
# =========================================================
if "research_store" not in st.session_state:
    st.session_state.research_store = {}
if "content_history" not in st.session_state:
    st.session_state.content_history = []

# =========================================================
# 6. SIDEBAR: PUSAT KAWALAN & EKSTRAK PDF KE SUPABASE
# =========================================================
st.sidebar.title("🎛️ Pusat Kawalan Produk")
selected_product = st.sidebar.selectbox("Pilih Produk:", list(DEFAULT_KNOWLEDGE.keys()))

st.sidebar.markdown("---")
st.sidebar.subheader("📄 Pangkalan Pengetahuan Produk")

saved_db_doc = get_saved_knowledge(selected_product)

if saved_db_doc:
    st.sidebar.success(f"💾 Dokumen Aktif di Database:\n**{saved_db_doc['pdf_name']}**")
    with st.sidebar.expander("Lihat Ringkasan dari Database"):
        st.caption(f"Dikemaskini pada: {saved_db_doc.get('updated_at', '-')}")
        st.write(saved_db_doc['extracted_content'])
else:
    st.sidebar.info("ℹ️ Belum ada fail PDF disimpan untuk produk ini. Menggunakan info asas.")

uploaded_pdf = st.sidebar.file_uploader(f"Pilih fail PDF baharu ({selected_product})", type=["pdf"])

if uploaded_pdf is not None:
    st.sidebar.caption(f"Fail dipilih: `{uploaded_pdf.name}`")
    if st.sidebar.button("🚀 Hantar & Simpan PDF ke Supabase", type="primary"):
        temp_file_path = None
        try:
            with st.sidebar.status("Sedang memproses & membaca PDF...", expanded=True) as status_box:
                st.write("1. Menyediakan fail ke pelayan...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded_pdf.getvalue())
                    temp_file_path = tmp.name

                st.write("2. Menghantar fail ke Google Files API...")
                gemini_file = client.files.upload(file=temp_file_path)

                while getattr(gemini_file, 'state', None) and gemini_file.state.name == "PROCESSING":
                    time.sleep(1)
                    gemini_file = client.files.get(name=gemini_file.name)

                st.write("3. Mengekstrak fakta mendalam (First-Principles Analysis)...")
                extract_prompt = f"""
                Bedah dokumen PDF ini untuk produk {selected_product}.
                Gunakan analisis First-Principles: Asingkan fakta sebenar daripada ayat promosi.
                
                Keluarkan struktur padat berikut:
                1. SENARAI PAKEJ & HARGA RASMI: Senaraikan pakej, kuota, dan harga tepat.
                2. CORE VALUE / USP: 3 nilai teras yang membezakan produk ini daripada pesaing.
                3. DEMOGRAFIK & AVATAR: Siapa yang paling rugi jika tidak melanggan/menggunakan produk ini?
                4. TERMA KRITIKAL & PANTANG LARANG: Syarat kelayakan dan perkara yang dilarang salah faham.
                """
                
                extracted_text = call_gemini(
                    contents=[gemini_file, extract_prompt],
                    system_instruction="Awak ialah Data Research Auditor yang mengekstrak maklumat perniagaan secara objektif dan tepat."
                )

                st.write("4. Menyimpan data kekal ke Supabase...")
                supabase.table("product_knowledge").upsert({
                    "product_name": selected_product,
                    "pdf_name": uploaded_pdf.name,
                    "extracted_content": extracted_text
                }).execute()

                status_box.update(label="✅ Selesai disimpan ke Supabase!", state="complete", expanded=False)

            st.sidebar.success(f"Berjaya! Dokumen `{uploaded_pdf.name}` kini kekal dalam pangkalan data.")
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.sidebar.error(f"❌ Ralat pemprosesan: {str(e)}")
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

st.sidebar.markdown("---")
with st.sidebar.expander("🤖 Status Model AI"):
    st.write(f"**Model Aktif:** `{MODEL_NAME}`")
    st.caption("Pelan Kuota: 500 permintaan sehari (Percuma).")

base_info = DEFAULT_KNOWLEDGE[selected_product]
with st.sidebar.expander("📌 Info Asas Sistem (Default)"):
    st.write(f"**USP:** {base_info['usp']}")
    st.write(f"**Sasaran:** {base_info['avatar']}")
    st.write(f"**Pematuhan:** {base_info['compliance']}")

if st.sidebar.button("Log Keluar"):
    st.session_state.authenticated = False
    st.rerun()

# =========================================================
# 7. PAPARAN UTAMA (L1 -> L2 -> L3 DENGAN STRATEGI 3)
# =========================================================
st.title(f"⚡ Command Center: {selected_product}")

knowledge_context = f"Maklumat Asas: {json.dumps(base_info)}\n"
if saved_db_doc:
    knowledge_context += f"\nMaklumat Tambahan Dokumen Rasmi ({saved_db_doc['pdf_name']}):\n{saved_db_doc['extracted_content']}"

# ---------------------------------------------------------
# TAHAP 1: TEAM RESEARCH (DEEP THINKING RESEARCH AGENT)
# ---------------------------------------------------------
st.markdown("### 🔍 Tahap 1: Laporan Kajian Pasaran (Research Hub)")

has_research = selected_product in st.session_state.research_store
status_label = "✅ Sedia dalam memori (Boleh terus guna di L2)" if has_research else "⚠️ Belum dijalankan untuk produk ini"
st.info(f"Status Kajian Produk **{selected_product}**: {status_label}")

col_r1, col_r2 = st.columns([3, 1])
with col_r1:
    research_focus = st.text_input(
        "Fokus Tambahan untuk Kajian Pasaran (Pilihan):", 
        placeholder="Contoh: Kaji trend penjimatan bil telefon atau cara jana pendapatan pasif"
    )
with col_r2:
    btn_research = st.button("Jana / Kemas Kini Research (L1) 🧠", type="secondary")

if btn_research:
    try:
        with st.spinner("Research Agent sedang membedah pasaran (First-Principles Thinking)..."):
            
            # 1. Payload Maklumat Produk & Fokus Tambahan
            prompt_payload = f"""
            Produk: {selected_product}
            Pangkalan Pengetahuan:
            {knowledge_context}
            
            Fokus Tambahan: {research_focus if research_focus else 'Kajian pasaran menyeluruh'}
            
            Tugasan Penyelidikan:
            1. Analisis Demografik & Psikografik sasaran di Malaysia.
            2. 3 Pain Points kritikal prospek (emosi, kewangan, masa).
            3. 3 Sudut Pemasaran (Angles) berserta ayat Hook pembuka.
            """

            # 2. ARAHAN SISTEM STRATEGI 3 (DEEP THINKING PROMPT)
            system_prompt_research = """
            Awak ialah Lead Market Strategist & Consumer Psychologist. 
            Gunakan kerangka pemikiran mendalam (First-Principles Thinking).

            Peraturan Analisis:
            1. JANGAN tulis ayat umum, klise, atau berbunga-bunga.
            2. Berikan analisis demografik dan psikografik yang spesifik untuk pasaran Malaysia (faktor gaji, kos sara hidup, gaya hidup).
            3. Berikan 'Pain Points' sebenar yang menyentuh emosi pembeli (ketakutan, kerugian masa, pembaziran wang).
            4. Setiap cadangan sudut pemasaran (Angle) MESTI disertakan dengan 'Hook' pembuka ayat yang kuat.
            """

            # 3. Panggil Model dengan Arahan Sistem Tersebut
            research_result = call_gemini(
                contents=prompt_payload,
                system_instruction=system_prompt_research
            )
            
            # Simpan ke session state supaya L2 boleh baca terus
            st.session_state.research_store[selected_product] = research_result
            st.success("Kajian L1 berjaya disimpan dalam memori!")
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Ralat Tahap 1: {str(e)}")

if has_research:
    with st.expander("📖 Lihat Dokumen Research L1 Terperinci"):
        st.markdown(st.session_state.research_store[selected_product])

st.markdown("---")

# ---------------------------------------------------------
# TAHAP 2 & 3: PENJANAAN KANDUNGAN & AUDIT QA AUTOMATIK
# ---------------------------------------------------------
st.markdown("### ✍️ Tahap 2 & 3: Penjanaan Kandungan & Semakan QA Automatik")

if not has_research:
    st.warning("Sila jalankan Tahap 1 (Research Hub) terlebih dahulu sebelum menjana kandungan.")
else:
    c1, c2 = st.columns(2)
    with c1:
        campaign_theme = st.text_input("Tema Kempen Hari Ini:", placeholder="Contoh: Kempen Gaji Masuk / Cuti Sekolah / Jimat Poket")
    with c2:
        angle_choice = st.selectbox("Gaya / Pendekatan:", [
            "Emosi & Storytelling (Kisah Kehidupan / Selesaikan Masalah)",
            "Direct Response (Tawaran Segera, Mendesak & Diskaun)",
            "Edukasi / Nilai Tambah (Tips Percuma & Kesedaran)"
        ])

    btn_content = st.button("Jana Draf Iklan Baru (L2) 🚀", type="primary")

    if btn_content:
        if not campaign_theme.strip():
            st.warning("Sila masukkan Tema Kempen sebelum menjana draf!")
        else:
            try:
                cached_research = st.session_state.research_store[selected_product]

                # 1. TAHAP 2: Content Agent (Dengan Prompt Gaya Copywriter Handal)
                with st.spinner("Content Agent sedang merangka salinan iklan memukau..."):
                    content_prompt = f"""
                    Produk: {selected_product}
                    Tema Kempen: {campaign_theme}
                    Pendekatan Pemasaran: {angle_choice}
                    Sumber Kajian Induk (L1):
                    {cached_research}

                    Tugasan:
                    1. Salinan Facebook Post:
                       - Hook pembuka yang mencengkam (Stop-scrolling hook).
                       - Penceritaan santai yang menyentuh emosi pembaca tempatan.
                       - Tawaran yang jelas dan Call-To-Action (CTA) yang mendesak.
                    2. Bebenang X / Twitter:
                       - Hook tweet pertama yang memukau.
                       - 3 tweet isi padat dan bersambung.
                       - Tweet penutup bersama CTA.
                    3. Konsep Visual:
                       - Deskripsi visual poster atau prompt jana gambar AI (gaya hiper-realistik/moden).
                    """
                    
                    content_instruction = """
                    Awak ialah Senior Direct-Response Copywriter berprestasi tinggi di Malaysia.
                    Gunakan Bahasa Melayu yang hidup, santai, beremosi, dan tidak kedengaran seperti teks terjemahan AI yang kaku.
                    Pastikan salinan iklan fokus kepada faedah pelanggan, bukan ciri teknikal semata-mata.
                    """
                    
                    draft_text = call_gemini(
                        contents=content_prompt,
                        system_instruction=content_instruction
                    )

                # 2. TAHAP 3: QA & Data Analyst Agent (Audit Ketat)
                with st.spinner("QA Agent sedang mengaudit etika & integriti iklan..."):
                    qa_prompt = f"""
                    Produk: {selected_product}
                    Peraturan Integriti & Compliance: {base_info['compliance']}
                    Draf Iklan yang Dihasilkan:
                    {draft_text}

                    Tugasan Audit Integriti:
                    1. Skor Kualiti & Keyakinan: Berikan skor 1 hingga 10.
                    2. Semakan Risiko & Etika: Semak jika ada overclaim, janji palsu, atau perkataan berisiko undang-undang.
                    3. Pembetulan Pantas: Nyatakan baris ayat yang perlu dibaiki jika ada kelemahan.
                    """
                    
                    qa_instruction = """
                    Awak ialah Chief Compliance Officer dan Advertising Ethics Auditor.
                    Bertindak tegas, jangan beri markah tinggi jika iklan mengelirukan atau melanggar pantang larang jenama.
                    """
                    
                    qa_report_text = call_gemini(
                        contents=qa_prompt,
                        system_instruction=qa_instruction
                    )

                # Simpan ke sejarah kempen
                st.session_state.content_history.insert(0, {
                    "product": selected_product,
                    "theme": campaign_theme,
                    "angle": angle_choice,
                    "content": draft_text,
                    "qa": qa_report_text
                })
                st.success("Kandungan berjaya dijana dan selesai diaudit oleh QA!")

            except Exception as e:
                st.error(f"❌ Ralat Penjanaan Kandungan: {str(e)}")

# Paparan arkib kempen
if st.session_state.content_history:
    st.markdown("---")
    st.subheader("📂 Arkib Draf Iklan & Laporan Audit Terkini")

    for i, item in enumerate(st.session_state.content_history):
        with st.container():
            st.markdown(f"#### 🏷️ #{len(st.session_state.content_history) - i} | [{item['product']}] {item['theme']} — *{item['angle']}*")
            tab_copy, tab_audit = st.tabs(["📝 Salinan Iklan & Visual (L2)", "⚖️ Laporan QA & Integriti (L3)"])
            with tab_copy:
                st.markdown(item["content"])
            with tab_audit:
                st.markdown(item["qa"])
            st.markdown("---")
