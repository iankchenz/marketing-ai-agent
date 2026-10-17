import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client
import json

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

# =========================================================
# 3. FUNGSI PANGGILAN MODEL DENGAN AUTO-FALLBACK
# =========================================================
# Senarai model yang disahkan oleh Google API & fail PDF
PRO_MODELS = ["gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-2.5-flash", "gemini-2.0-flash"]
FLASH_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.1-pro-preview"]

def call_gemini(contents, system_instruction=None, is_pro=True):
    model_list = PRO_MODELS if is_pro else FLASH_MODELS
    last_error = None
    
    config = types.GenerateContentConfig()
    if system_instruction:
        config.system_instruction = system_instruction

    for m in model_list:
        try:
            response = client.models.generate_content(
                model=m,
                contents=contents,
                config=config
            )
            return response.text
        except Exception as e:
            last_error = e
            continue
            
    raise RuntimeError(f"Gagal memanggil model Google Gemini: {last_error}")

# =========================================================
# 4. PENGKALAN DATA PRODUK ASAS (DEFAULT KNOWLEDGE)
# =========================================================
DEFAULT_KNOWLEDGE = {
    "Tone Wow": {
        "kategori": "Telco & Pendapatan Pasif",
        "usp": "Simkad prabayar pelan data jimat yang memberi insentif komisen rujukan setiap kali pengguna topup.",
        "avatar": "Pengguna telefon pintar yang ingin kurangkan beban bil & individu mencari pendapatan sampingan.",
        "compliance": "Dilarang janjikan pendapatan goyang kaki atau guna istilah skim cepat kaya / skim piramid."
    },
    "Eastel": {
        "kategori": "Telco Mampu Milik",
        "usp": "Penyedia pelan internet pantas dengan kuota besar pada kadar mampu milik mesra poket.",
        "avatar": "Pelajar, penghantar makanan / gig workers, dan keluarga yang mengutamakan penjimatan.",
        "compliance": "Fokus pada kestabilan liputan dan penjimatan kos bulanan."
    },
    "Produk AI": {
        "kategori": "Automasi & Perisian AI",
        "usp": "Sistem ejen pintar untuk automasi copywriting, analisis data, dan sokongan pemasaran bisnes.",
        "avatar": "Pemilik bisnes PKS, usahawan solo, dan pencipta kandungan digital.",
        "compliance": "Jangan buat kenyataan palsu (overclaim) bahawa AI menggantikan 100% manusia tanpa semakan fakta."
    },
    "BeliBeliOnline": {
        "kategori": "Marketplace & E-Commerce Tempatan",
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
# 5. INISIALISASI SESI (SESSION STATE)
# =========================================================
if "research_store" not in st.session_state:
    st.session_state.research_store = {}
if "content_history" not in st.session_state:
    st.session_state.content_history = []

# =========================================================
# 6. SIDEBAR: PENGURUSAN PRODUK & MUAT NAIK PDF
# =========================================================
st.sidebar.title("🎛️ Pusat Kawalan Produk")
selected_product = st.sidebar.selectbox("Pilih Produk:", list(DEFAULT_KNOWLEDGE.keys()))

st.sidebar.markdown("---")
st.sidebar.subheader("📄 Kemas Kini Pengetahuan Produk")

saved_db_doc = get_saved_knowledge(selected_product)

if saved_db_doc:
    st.sidebar.success(f"💾 Dokumen Aktif di Database:\n**{saved_db_doc['pdf_name']}**")
    with st.sidebar.expander("Lihat Ringkasan dari Database"):
        st.caption(f"Dikemaskini pada: {saved_db_doc.get('updated_at', '-')}")
        st.write(saved_db_doc['extracted_content'])
else:
    st.sidebar.info("ℹ️ Belum ada dokumen PDF disimpan untuk produk ini. Menggunakan maklumat asas.")

uploaded_pdf = st.sidebar.file_uploader(f"Pilih fail PDF baharu ({selected_product})", type=["pdf"])

if uploaded_pdf is not None:
    st.sidebar.caption(f"Fail dipilih: `{uploaded_pdf.name}`")
    if st.sidebar.button("🚀 Hantar & Simpan PDF ke Supabase", type="primary"):
        with st.sidebar.status("Sedang memproses & mengekstrak data...", expanded=True) as status_box:
            st.write("1. Membaca data fail PDF...")
            pdf_bytes = uploaded_pdf.getvalue()
            pdf_part = types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf"
            )
            
            st.write("2. Gemini sedang menganalisis dokumen...")
            extract_prompt = f"""
            Ekstrak semua maklumat penting daripada PDF ini untuk dijadikan pangkalan pengetahuan produk {selected_product}:
            1. Pakej, Pelan & Harga Terkini.
            2. Kelebihan Unik (USP) & Tawaran Tambahan.
            3. Avatar / Sasaran Pelanggan Tepat.
            4. Pantang Larang & Terma Penting.
            Sediakan ringkasan dalam bentuk poin fakta yang padat dan terperinci.
            """
            
            extracted_text = call_gemini(
                contents=[pdf_part, extract_prompt],
                system_instruction="Awak ialah pakar pengekstrakan data dokumen dan maklumat produk.",
                is_pro=True
            )
            
            st.write("3. Menyimpan terus ke Pangkalan Data Supabase...")
            supabase.table("product_knowledge").upsert({
                "product_name": selected_product,
                "pdf_name": uploaded_pdf.name,
                "extracted_content": extracted_text
            }).execute()
            
            status_box.update(label="✅ Selesai disimpan ke Supabase!", state="complete", expanded=False)
            
        st.sidebar.success(f"Berjaya! Dokumen `{uploaded_pdf.name}` kini kekal dalam pangkalan data.")
        st.rerun()

st.sidebar.markdown("---")
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

knowledge_context = f"Maklumat Asas: {json.dumps(base_info)}\n"
if saved_db_doc:
    knowledge_context += f"\nMaklumat Tambahan Dokumen Rasmi ({saved_db_doc['pdf_name']}):\n{saved_db_doc['extracted_content']}"

# ---------------------------------------------------------
# TAHAP 1: TEAM RESEARCH (Jalankan Sekali / Cached)
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
    with st.spinner("Research Agent sedang membedah pasaran & membaca dokumen dari Supabase..."):
        prompt_payload = f"""
        Produk: {selected_product}
        Pangkalan Pengetahuan:
        {knowledge_context}
        
        Fokus Tambahan: {research_focus if research_focus else 'Kajian pasaran menyeluruh'}
        
        Tugasan: Sediakan Customer Avatar terperinci, senaraikan 3 Masalah Utama (Pain Points), dan cadangkan 3 Sudut Pemasaran (Angles) yang paling berkesan di Malaysia.
        """

        research_result = call_gemini(
            contents=prompt_payload,
            system_instruction="Awak ialah Market Research Specialist berpengalaman luas dalam pasaran tempatan Malaysia.",
            is_pro=True
        )
        st.session_state.research_store[selected_product] = research_result
        st.success("Kajian L1 berjaya disimpan dalam memori!")
        st.rerun()

if has_research:
    with st.expander("📖 Lihat Dokumen Research L1 Terperinci"):
        st.markdown(st.session_state.research_store[selected_product])

st.markdown("---")

# ---------------------------------------------------------
# TAHAP 2 & 3: PENJANAAN KANDUNGAN & SEMAKAN QA
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
            cached_research = st.session_state.research_store[selected_product]

            # 1. TAHAP 2: Content & Visual Agent (Flash)
            with st.spinner("Content Agent sedang mengarang copywriting & visual..."):
                content_prompt = f"""
                Produk: {selected_product}
                Tema Kempen: {campaign_theme}
                Pendekatan Pemasaran: {angle_choice}
                Sumber Kajian Induk (L1):
                {cached_research}

                Tugasan:
                1. Tulis 1 salinan Facebook Post yang santai, memikat jiwa, dan ada Call-To-Action (CTA) jelas.
                2. Tulis 1 bebenang X / Twitter yang pendek dan padat (Hook + Isi + CTA).
                3. Berikan 1 cadangan Visual (Prompt imej AI atau konsep poster Canva).
                """
                draft_text = call_gemini(
                    contents=content_prompt,
                    system_instruction="Awak ialah Senior Copywriter dan Creative Director di Malaysia.",
                    is_pro=False
                )

            # 2. TAHAP 3: QA & Data Analyst Agent (Pro)
            with st.spinner("QA Agent sedang mengaudit kualiti, fakta & integriti iklan..."):
                qa_prompt = f"""
                Produk: {selected_product}
                Peraturan Integriti & Compliance: {base_info['compliance']}
                Draf Iklan yang Dihasilkan:
                {draft_text}

                Tugasan:
                1. Berikan Skor Kualiti (1 hingga 10).
                2. Semak jika ada overclaim, kenyataan palsu, atau risiko melanggar etika.
                3. Berikan komen penambahbaikan ringkas.
                """
                qa_report_text = call_gemini(
                    contents=qa_prompt,
                    system_instruction="Awak ialah Data Analyst & QA Compliance Officer yang sangat teliti dan beretika.",
                    is_pro=True
                )

            # Simpan rekod kempen
            st.session_state.content_history.insert(0, {
                "product": selected_product,
                "theme": campaign_theme,
                "angle": angle_choice,
                "content": draft_text,
                "qa": qa_report_text
            })
            st.success("Kandungan berjaya dijana dan selesai diaudit oleh QA!")

# Paparan arkib
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
