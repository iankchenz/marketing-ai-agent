import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client
import json
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

MODEL_NAME = "gemini-3.1-flash-lite"

# =========================================================
# 3. ENJIN PANGGILAN AI
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
# 4. PENGKALAN DATA PRODUK ASAS (DEFAULT KNOWLEDGE)
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

if saved_db_doc and saved_db_doc.get("pdf_name"):
    st.sidebar.success(f"💾 Dokumen Aktif di Database:\n**{saved_db_doc['pdf_name']}**")
    with st.sidebar.expander("Lihat Ringkasan dari Database"):
        st.caption(f"Dikemaskini pada: {saved_db_doc.get('updated_at', '-')}")
        st.write(saved_db_doc.get('extracted_content', 'Tiada ringkasan'))
else:
    st.sidebar.info(f"ℹ️ Belum ada fail PDF disimpan untuk {selected_product}. Menggunakan maklumat asas.")

uploaded_pdf = st.sidebar.file_uploader(
    f"Pilih fail PDF baharu ({selected_product})", 
    type=["pdf"],
    help="Pilih fail dokumen spesifikasi produk rasmi"
)

if uploaded_pdf is not None:
    file_size_kb = len(uploaded_pdf.getvalue()) / 1024
    st.sidebar.caption(f"📁 Fail sedia: `{uploaded_pdf.name}` ({file_size_kb:.1f} KB)")
    
    if st.sidebar.button("🚀 Hantar & Simpan PDF ke Supabase", type="primary", use_container_width=True):
        try:
            with st.sidebar.status("Sedang memproses & mengekstrak data...", expanded=True) as status_box:
                st.write("1. Membaca data fail PDF...")
                pdf_bytes = uploaded_pdf.getvalue()
                pdf_part = types.Part.from_bytes(
                    data=pdf_bytes,
                    mime_type="application/pdf"
                )
                
                st.write("2. Memproses dokumen dengan Gemini 3.1 Flash-Lite...")
                extract_prompt = f"""
                Bedah dokumen PDF ini untuk produk {selected_product}:
                1. SENARAI PAKEJ & HARGA RASMI: Senaraikan pakej, kuota, dan harga tepat.
                2. CORE VALUE / USP: 3 nilai teras yang membezakan produk ini daripada pesaing.
                3. DEMOGRAFIK & SASARAN AVATAR: Siapa prospek utama di Malaysia?
                4. TERMA KRITIKAL & PANTANG LARANG: Syarat kelayakan dan perkara yang dilarang salah faham.
                
                Hasilkan rumusan dalam poin fakta padat tanpa ayat promosi kosong.
                """
                
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[pdf_part, extract_prompt],
                    config=types.GenerateContentConfig(
                        system_instruction="Awak ialah Data Auditor yang mengekstrak fakta produk secara tepat dan objektif."
                    )
                )
                extracted_text = response.text
                
                st.write("3. Menolak data kekal ke Supabase...")
                supabase.table("product_knowledge").upsert({
                    "product_name": selected_product,
                    "pdf_name": uploaded_pdf.name,
                    "extracted_content": extracted_text
                }).execute()
                
                status_box.update(label="✅ Selesai disimpan ke Supabase!", state="complete", expanded=False)
            
            st.sidebar.success(f"Tahniah! Dokumen `{uploaded_pdf.name}` kini kekal disimpan di Supabase.")
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.sidebar.error(f"❌ Ralat semasa proses: {str(e)}")

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
# 7. PAPARAN UTAMA (L1 -> L2 -> L3)
# =========================================================
st.title(f"⚡ Command Center: {selected_product}")

# Bina konteks pangkalan data yang lengkap
knowledge_context = f"Maklumat Asas Produk:\n{json.dumps(base_info, ensure_ascii=False, indent=2)}\n"
if saved_db_doc and saved_db_doc.get("extracted_content"):
    knowledge_context += f"\nMaklumat Tambahan daripada Dokumen Rasmi ({saved_db_doc.get('pdf_name')}):\n{saved_db_doc['extracted_content']}"

# Semak laporan L1 yang tersimpan di Supabase
persisted_l1_research = saved_db_doc.get("l1_research") if saved_db_doc else None

# ---------------------------------------------------------
# TAHAP 1: TEAM RESEARCH (KEKAL DI SUPABASE)
# ---------------------------------------------------------
st.markdown("### 🔍 Tahap 1: Laporan Kajian Pasaran (Research Hub)")

if persisted_l1_research:
    st.success("✅ Laporan L1 sedia ada di Database! (L2 & L3 akan terus menggunakan rujukan ini)")
else:
    st.info("ℹ️ Belum ada laporan L1 tersimpan untuk produk ini di Database. Sila jana sekali untuk rujukan berterusan.")

col_r1, col_r2 = st.columns([3, 1])
with col_r1:
    research_focus = st.text_input(
        "Fokus Tambahan untuk Kajian Pasaran (Pilihan):", 
        placeholder="Contoh: Kaji trend penjimatan bil telefon atau cara jana pendapatan pasif"
    )
with col_r2:
    btn_research = st.button("Jana / Kemas Kini Research (L1) 🧠", type="secondary", use_container_width=True)

if btn_research:
    try:
        with st.spinner("Research Agent sedang menganalisis pasaran & menyimpan ke Supabase..."):
            prompt_payload = f"""
            Produk: {selected_product}
            Pangkalan Pengetahuan Rasmi (Database):
            {knowledge_context}
            
            Fokus Tambahan: {research_focus if research_focus else 'Kajian pasaran menyeluruh'}
            
            Tugasan Penyelidikan Mendalam:
            1. PSIKOGRAFIK AVATAR: Analisis ketakutan (fears), keraguan (objections), dan matlamat hidup mereka di Malaysia.
            2. 3 PAIN POINTS KRITIKAL: Terangkan masalah sebenar mereka dengan situasi realiti harian.
            3. 3 SUDUT PENDEKATAN (ANGLES): Cadangkan 3 sudut pemasaran unik yang menyentuh emosi berserta 1 cadangan 'Hook' pembuka bagi setiap sudut.
            """

            system_prompt_research = """
            Awak ialah Lead Market Strategist & Consumer Psychologist. 
            Gunakan kerangka pemikiran mendalam (First-Principles Thinking).

            Peraturan Analisis:
            1. JANGAN tulis ayat umum, klise, atau berbunga-bunga.
            2. Berikan analisis demografik dan psikografik yang spesifik untuk pasaran Malaysia (faktor gaji, kos sara hidup, gaya hidup).
            3. Berikan 'Pain Points' sebenar yang menyentuh emosi pembeli (ketakutan, kerugian masa, pembaziran wang).
            4. Setiap cadangan sudut pemasaran (Angle) MESTI disertakan dengan 'Hook' pembuka ayat yang kuat.
            """

            research_result = call_gemini(
                contents=prompt_payload,
                system_instruction=system_prompt_research
            )
            
            # SIMPAN KEKAL KE SUPABASE
            supabase.table("product_knowledge").upsert({
                "product_name": selected_product,
                "l1_research": research_result
            }).execute()
            
            st.success("Kajian L1 berjaya disimpan secara kekal ke Supabase!")
            time.sleep(1)
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Ralat Tahap 1: {str(e)}")

if persisted_l1_research:
    with st.expander("📖 Lihat Dokumen Research L1 Terperinci (Dari Supabase)"):
        st.markdown(persisted_l1_research)

st.markdown("---")

# ---------------------------------------------------------
# TAHAP 2 & 3: PENJANAAN KANDUNGAN & AUDIT QA AUTOMATIK
# ---------------------------------------------------------
st.markdown("### ✍️ Tahap 2 & 3: Penjanaan Kandungan & Semakan QA Automatik")

col_ui1, col_ui2, col_ui3 = st.columns([1.5, 1.2, 1.3])

with col_ui1:
    theme_type = st.selectbox(
        "Tema Kempen:",
        [
            "Umum / Evergreen (Kelebihan Teras & USP)",
            "Kempen Hari Gaji (Payday Special)",
            "Kempen Cuti Sekolah & Musim Cuti",
            "Kempen Jimat Poket / Kenaikan Kos Sara Hidup",
            "Tulis Tema Sendiri (Custom)..."
        ]
    )
    if theme_type == "Tulis Tema Sendiri (Custom)...":
        custom_theme = st.text_input("Nyatakan Tema Khusus:", placeholder="Contoh: Promosi Awal Tahun / Pakej Ejen")
        selected_theme = custom_theme if custom_theme.strip() else "Kempen Khas"
    elif theme_type == "Umum / Evergreen (Kelebihan Teras & USP)":
        selected_theme = "Umum / Evergreen (Fokus kepada penyelesaian masalah harian tanpa kempen bermusim)"
    else:
        selected_theme = theme_type

with col_ui2:
    platform_choice = st.selectbox(
        "Platform Sasaran:",
        [
            "Semua Platform (FB, X & Threads)",
            "Facebook Page Sahaja",
            "X (Twitter) Sahaja",
            "Threads Sahaja"
        ]
    )

with col_ui3:
    angle_choice = st.selectbox("Gaya / Pendekatan:", [
        "Emosi & Storytelling (Kisah Kehidupan / Selesaikan Masalah)",
        "Direct Response (Tawaran Segera, Mendesak & Diskaun)",
        "Edukasi / Nilai Tambah (Tips Percuma & Kesedaran)"
    ])

btn_content = st.button("Jana Draf Iklan Baru (L2 & L3) 🚀", type="primary", use_container_width=True)

if btn_content:
    try:
        # Gunakan laporan L1 jika ada, atau maklumkan fallback
        l1_source_text = persisted_l1_research if persisted_l1_research else "Tiada laporan L1 terdahulu. Rujuk fakta teras produk sepenuhnya."

        platform_tasks = []
        if platform_choice in ["Facebook Page Sahaja", "Semua Platform (FB, X & Threads)"]:
            platform_tasks.append("- SALINAN FACEBOOK PAGE: Stop-scrolling hook yang menarik, penceritaan beremosi, tawaran nilai jelas, dan Call-To-Action (CTA).")
        if platform_choice in ["X (Twitter) Sahaja", "Semua Platform (FB, X & Threads)"]:
            platform_tasks.append("- BEBENANG X / TWITTER: Tweet hook pembuka yang padat, 3 tweet isi bernilai, dan tweet penutup dengan CTA.")
        if platform_choice in ["Threads Sahaja", "Semua Platform (FB, X & Threads)"]:
            platform_tasks.append("- SALINAN THREADS: Gaya perbualan santai / POV tempatan, mencetuskan interaksi/komen komuniti, dan CTA bersahaja.")
        platform_tasks.append("- KONSEP VISUAL: 1 cadangan visual poster Canva atau prompt jana imej AI bersesuaian.")

        tasks_text = "\n".join(platform_tasks)

        # ---------------------------------------------------------
        # LANGKAH 1: Content Agent (L2) - Mengunci DB + L1
        # ---------------------------------------------------------
        with st.spinner(f"Content Agent sedang mengarang (Merujuk Database & L1)..."):
            content_prompt = f"""
            Produk: {selected_product}
            Tema Kempen: {selected_theme}
            Pendekatan Pemasaran: {angle_choice}
            Platform Terlibat: {platform_choice}

            =======================================================
            SUMBER RUJUKAN 1: FAKTA RASMI & DOKUMEN DATABASE SUPABASE
            =======================================================
            {knowledge_context}

            =======================================================
            SUMBER RUJUKAN 2: STRATEGI KAJIAN PASARAN L1 (JIKA ADA)
            =======================================================
            {l1_source_text}

            TUGASAN:
            Hasilkan salinan iklan berkualiti tinggi berdasarkan Rujukan 1 & 2 di atas.
            {tasks_text}
            """

            content_instruction = """
            Awak ialah Senior Direct-Response Copywriter di Malaysia.
            PENTING: Semua tawaran, harga, ciri produk, dan terma MESTI patuh kepada SUMBER RUJUKAN 1 (Database).
            Gunakan Bahasa Melayu yang hidup, santai, beremosi, dan relevan dengan budaya tempatan.
            Hanya hasilkan kandungan bagi platform yang diminta sahaja.
            """

            draft_text = call_gemini(
                contents=content_prompt,
                system_instruction=content_instruction
            )

        # ---------------------------------------------------------
        # LANGKAH 2: QA & Auto-Correction Agent (L3) - Mengunci DB + Compliance
        # ---------------------------------------------------------
        with st.spinner("QA Agent sedang mengaudit & menyediakan versi siap sedia siar..."):
            qa_prompt = f"""
            Produk: {selected_product}
            Peraturan Pematuhan & Fakta Database:
            {knowledge_context}

            Platform Terlibat: {platform_choice}
            Draf Iklan Asal (L2):
            {draft_text}

            Tugasan QA:
            1. Sediakan Laporan Audit Integriti (Skor 1-10, semakan fakta mengikut database, semakan overclaim, dan ulasan penambahbaikan).
            2. TULIS SEMULA (REWRITE) draf iklan di atas menjadi versi yang telah dibaiki 100% (bebas overclaim, nada lebih meyakinkan, format kemas, sedia untuk terus disiarkan).

            Format Output Wajib:
            Tulis laporan audit dahulu, kemudian letakkan pemisah tepat '===REVISED_COPY===' dan sertakan salinan iklan yang telah dibaiki sepenuhnya selepas pemisah tersebut.
            """

            qa_instruction = """
            Awak ialah Chief Compliance Officer merangkap Senior Editor. 
            Semak draf iklan dengan merujuk ketat kepada Fakta Database.
            Pastikan versi REVISED_COPY bebas daripada kesalahan fakta, tidak melanggar etika, dan sedia untuk terus disiarkan oleh peniaga.
            """

            raw_qa_output = call_gemini(
                contents=qa_prompt,
                system_instruction=qa_instruction
            )

            if "===REVISED_COPY===" in raw_qa_output:
                parts = raw_qa_output.split("===REVISED_COPY===")
                qa_report_text = parts[0].strip()
                corrected_copy_text = parts[1].strip()
            else:
                qa_report_text = raw_qa_output
                corrected_copy_text = draft_text

        st.session_state.content_history.insert(0, {
            "product": selected_product,
            "theme": selected_theme,
            "platform": platform_choice,
            "angle": angle_choice,
            "content_original": draft_text,
            "qa_report": qa_report_text,
            "content_corrected": corrected_copy_text
        })
        st.success("Kandungan berjaya dijana & diaudit mengikut dokumen Database!")

    except Exception as e:
        st.error(f"❌ Ralat Penjanaan Kandungan: {str(e)}")

# ---------------------------------------------------------
# PAPARAN ARKIB (3 TAB)
# ---------------------------------------------------------
if st.session_state.content_history:
    st.markdown("---")
    st.subheader("📂 Arkib Draf Iklan & Versi Siap Audit")

    for i, item in enumerate(st.session_state.content_history):
        with st.container():
            st.markdown(f"#### 🏷️ #{len(st.session_state.content_history) - i} | [{item['product']}] {item['theme']}")
            st.caption(f"📌 Platform: **{item['platform']}** | Gaya: **{item['angle']}**")
            
            tab_final, tab_copy, tab_audit = st.tabs([
                "✨ Salinan Siap Audit (Sedia Siar)",
                "📝 Draf Asal (L2)", 
                "⚖️ Laporan QA & Integriti (L3)"
            ])
            
            with tab_final:
                st.info("💡 Versi ini telah diselaraskan dengan fakta rasmi Database dan garis panduan pematuhan jenama.")
                st.markdown(item["content_corrected"])
            
            with tab_copy:
                st.markdown(item["content_original"])
                
            with tab_audit:
                st.markdown(item["qa_report"])
                
            st.markdown("---")
