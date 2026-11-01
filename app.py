import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client
import json
import time
import requests
import io
from pypdf import PdfReader

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

# Senarai Model AI Mengikut Keutamaan (Auto-Fallback Kalis 503 & 404)
MODEL_POOL = [
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-2.0-flash"
]

# =========================================================
# 3. FUNGSI UTILITI AI, PDF & TELEGRAM
# =========================================================
def extract_text_from_pdf_bytes(pdf_bytes):
    """Ekstrak teks PDF secara lokal untuk jimat bandwidth & cegah ralat 503."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        extracted_text = ""
        # Baca maksimum 15 muka surat pertama untuk mengelakkan token melimpah
        max_pages = min(len(reader.pages), 15)
        for i in range(max_pages):
            t = reader.pages[i].extract_text()
            if t:
                extracted_text += t + "\n"
        return extracted_text.strip()
    except Exception:
        return ""

def call_gemini(contents, system_instruction=None, max_retries=3):
    """Panggil Gemini dengan pusingan model bertingkat jika berlaku ralat 503 atau 429."""
    config = types.GenerateContentConfig()
    if system_instruction:
        config.system_instruction = system_instruction

    last_err = None

    for model_name in MODEL_POOL:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )
                return response.text
            except Exception as e:
                last_err = e
                err_msg = str(e)
                if any(k in err_msg for k in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]):
                    if attempt < max_retries - 1:
                        time.sleep((attempt + 1) * 2)
                        continue
                break

    raise last_err

def send_telegram_message(bot_token, chat_id, message_text):
    """Hantar mesej ke Telegram dengan fallback jika parsing markdown gagal."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown"
    }
    res = requests.post(url, json=payload, timeout=10)
    data = res.json()
    
    if not data.get("ok"):
        payload.pop("parse_mode", None)
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        
    return data

# =========================================================
# 4. PENGKALAN DATA PRODUK ASAS & FUNGSI SUPABASE
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

def get_product_documents(product_name):
    """Ambil semua fail dokumen tersimpan bagi produk ini."""
    try:
        res = supabase.table("product_documents")\
            .select("*")\
            .eq("product_name", product_name)\
            .order("created_at", desc=True)\
            .execute()
        return res.data if res.data else []
    except Exception as e:
        st.sidebar.error(f"Ralat capaian fail: {e}")
        return []

def get_all_uploaded_docs_summary():
    """Ambil senarai semua dokumen rentas produk untuk arkib sidebar."""
    try:
        res = supabase.table("product_documents")\
            .select("product_name, pdf_name, created_at")\
            .order("created_at", desc=True)\
            .execute()
        return res.data if res.data else []
    except Exception:
        return []

def get_saved_l1_research(product_name):
    """Ambil laporan L1 tersimpan dari jadual product_knowledge."""
    try:
        res = supabase.table("product_knowledge").select("l1_research").eq("product_name", product_name).execute()
        if res.data and len(res.data) > 0:
            return res.data[0].get("l1_research")
    except Exception as e:
        st.sidebar.error(f"Ralat capaian L1: {e}")
    return None

# =========================================================
# 5. INISIALISASI SESI
# =========================================================
if "content_history" not in st.session_state:
    st.session_state.content_history = []

if "poster_history" not in st.session_state:
    st.session_state.poster_history = []

# =========================================================
# 6. SIDEBAR: PUSAT KAWALAN & MULTIPLE PDF UPLOAD
# =========================================================
st.sidebar.title("🎛️ Pusat Kawalan Produk")
selected_product = st.sidebar.selectbox("Pilih Produk:", list(DEFAULT_KNOWLEDGE.keys()))

st.sidebar.markdown("---")
st.sidebar.subheader("📄 Pangkalan Dokumen Produk")

current_docs = get_product_documents(selected_product)

if current_docs:
    st.sidebar.success(f"💾 {len(current_docs)} Dokumen Tersimpan ({selected_product}):")
    for d in current_docs:
        with st.sidebar.expander(f"📄 {d['pdf_name']}"):
            st.caption(f"Dimuat naik: {d.get('created_at', '-')[:10]}")
            st.write(d.get("extracted_content", "Tiada kandungan"))
else:
    st.sidebar.info(f"ℹ️ Belum ada fail PDF untuk {selected_product}.")

# Widget Muat Naik Berbilang Dokumen
uploaded_pdfs = st.sidebar.file_uploader(
    f"Pilih fail PDF baharu ({selected_product})", 
    type=["pdf"],
    accept_multiple_files=True,
    help="Boleh pilih satu atau beberapa fail PDF serentak"
)

if uploaded_pdfs:
    st.sidebar.caption(f"📁 {len(uploaded_pdfs)} fail dipilih sedia diproses.")
    
    if st.sidebar.button("🚀 Hantar & Simpan Semua PDF", type="primary", use_container_width=True):
        with st.sidebar.status("Sedang memproses dokumen...", expanded=True) as status_box:
            for idx, pdf_file in enumerate(uploaded_pdfs):
                st.write(f"Mengekstrak ({idx+1}/{len(uploaded_pdfs)}): `{pdf_file.name}`...")
                
                pdf_bytes = pdf_file.getvalue()
                local_text = extract_text_from_pdf_bytes(pdf_bytes)
                
                # Hadkan teks kepada 12,000 aksara terawal bagi meringankan beban AI
                if len(local_text) > 12000:
                    local_text = local_text[:12000] + "\n...[Teks diringkaskan untuk pengoptimuman token]..."

                extract_prompt = f"""
                Bedah dokumen ini untuk produk {selected_product}:
                1. SENARAI PAKEJ & HARGA RASMI: Senaraikan pakej, kuota, dan harga tepat.
                2. CORE VALUE / USP: 3 nilai teras yang membezakan produk ini daripada pesaing.
                3. DEMOGRAFIK & SASARAN AVATAR: Siapa sasaran prospek utama di Malaysia?
                4. TERMA KRITIKAL & PANTANG LARANG: Syarat kelayakan dan perkara yang dilarang salah faham.
                
                Hasilkan rumusan dalam poin fakta padat tanpa ayat promosi kosong.
                """
                
                extracted_result = ""
                try:
                    if local_text and len(local_text) > 100:
                        ai_payload = f"Teks Dokumen:\n{local_text}\n\nArahan:\n{extract_prompt}"
                    else:
                        pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
                        ai_payload = [pdf_part, extract_prompt]

                    extracted_result = call_gemini(
                        contents=ai_payload,
                        system_instruction="Awak ialah Data Auditor yang mengekstrak fakta produk secara tepat dan objektif."
                    )
                except Exception:
                    # Penyelamat automatik jika pelayan Google sesak
                    if local_text and len(local_text) > 50:
                        extracted_result = f"[EKSTRAK TEKS TERUS]:\n\n{local_text}"
                    else:
                        extracted_result = f"Dokumen `{pdf_file.name}` didaftarkan secara rasmi."

                supabase.table("product_documents").insert({
                    "product_name": selected_product,
                    "pdf_name": pdf_file.name,
                    "extracted_content": extracted_result
                }).execute()

            status_box.update(label="✅ Semua fail berjaya diproses & disimpan!", state="complete", expanded=False)
        
        st.sidebar.success(f"Berjaya simpan {len(uploaded_pdfs)} fail ke Supabase!")
        time.sleep(1)
        st.rerun()

# Arkib Ringkasan Semua Dokumen
st.sidebar.markdown("---")
with st.sidebar.expander("📂 Arkib Semua Dokumen di Database", expanded=False):
    all_summary = get_all_uploaded_docs_summary()
    if all_summary:
        for item in all_summary:
            st.markdown(f"**• {item['product_name']}**")
            st.caption(f"📄 `{item['pdf_name']}` ({item['created_at'][:10]})")
    else:
        st.caption("Pangkalan data dokumen masih kosong.")

st.sidebar.markdown("---")
with st.sidebar.expander("🤖 Status Model AI"):
    st.write(f"**Model Utama:** `{MODEL_POOL[0]}`")
    st.write(f"**Model Sandaran:** `{MODEL_POOL[1]}`, `{MODEL_POOL[2]}`")
    st.caption("Sistem kuota percuma Google AI Studio.")

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

# Mengumpulkan teks rujukan daripada kesemua fail PDF produk aktif
pdf_knowledge_blocks = []
for d in current_docs:
    pdf_knowledge_blocks.append(f"--- Rujukan Dokumen: {d['pdf_name']} ---\n{d['extracted_content']}")

all_pdf_knowledge = "\n\n".join(pdf_knowledge_blocks)

knowledge_context = f"Maklumat Asas Produk:\n{json.dumps(base_info, ensure_ascii=False, indent=2)}\n"
if all_pdf_knowledge:
    knowledge_context += f"\nMaklumat Tambahan daripada Dokumen Rasmi ({len(current_docs)} Fail):\n{all_pdf_knowledge}"

persisted_l1_research = get_saved_l1_research(selected_product)

# ---------------------------------------------------------
# TAHAP 1: TEAM RESEARCH (CROSS-CHECK DOKUMEN PDF SUPABASE)
# ---------------------------------------------------------
st.markdown("### 🔍 Tahap 1: Laporan Kajian Pasaran (Research Hub)")

if persisted_l1_research:
    st.success("✅ Laporan L1 sedia ada di Database! (L2, L3 & Poster Generator merujuk fail ini secara automatik)")
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
        with st.spinner("Research Agent sedang membedah dokumen PDF & pasaran ke Supabase..."):
            prompt_payload = f"""
            Produk: {selected_product}
            Pangkalan Pengetahuan Rasmi (Database Dokumen PDF):
            {knowledge_context}
            
            Fokus Tambahan: {research_focus if research_focus else 'Kajian pasaran menyeluruh'}
            
            Tugasan Penyelidikan Mendalam:
            1. PSIKOGRAFIK AVATAR: Analisis ketakutan (fears), keraguan (objections), dan matlamat hidup mereka di Malaysia berdasarkan tawaran dokumen PDF.
            2. 3 PAIN POINTS KRITIKAL: Terangkan masalah sebenar mereka dengan situasi realiti harian.
            3. 3 SUDUT PENDEKATAN (ANGLES): Cadangkan 3 sudut pemasaran unik yang menyentuh emosi berserta 1 cadangan 'Hook' pembuka bagi setiap sudut.
            """

            system_prompt_research = """
            Awak ialah Lead Market Strategist & Consumer Psychologist. 
            Gunakan kerangka pemikiran First-Principles.
            Peraturan Analisis:
            1. JANGAN tulis ayat klise atau umum.
            2. Analisis demografik & psikografik spesifik pasaran Malaysia (kos sara hidup, gaji, beban harian).
            3. Wajib selaraskan sudut hujah dengan fakta tepat daripada dokumen PDF rasmi.
            """

            research_result = call_gemini(
                contents=prompt_payload,
                system_instruction=system_prompt_research
            )
            
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

# 4 Kolum: Termasuk Pilihan Bilangan Bahan (1 - 5 Bahan)
col_ui1, col_ui2, col_ui3, col_ui4 = st.columns([1.4, 1.1, 1.1, 0.7])

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

with col_ui4:
    num_copies = st.selectbox("Jumlah Draf:", [1, 2, 3, 4, 5], index=0, help="Berapa bahan/variasi berbeza yang mahu dihasilkan serentak")

btn_content = st.button("Jana Draf Iklan Baru (L2 & L3) 🚀", type="primary", use_container_width=True)

if btn_content:
    try:
        l1_source_text = persisted_l1_research if persisted_l1_research else "Tiada laporan L1 terdahulu. Rujuk fakta teras produk sepenuhnya."

        platform_tasks = []
        if platform_choice in ["Facebook Page Sahaja", "Semua Platform (FB, X & Threads)"]:
            platform_tasks.append("- SALINAN FACEBOOK PAGE: Stop-scrolling hook yang menarik, penceritaan beremosi, tawaran nilai jelas, dan Call-To-Action (CTA).")
        if platform_choice in ["X (Twitter) Sahaja", "Semua Platform (FB, X & Threads)"]:
            platform_tasks.append("- BEBENANG X / TWITTER: Tweet hook pembuka yang padat, 3 tweet isi bernilai, dan tweet penutup dengan CTA.")
        if platform_choice in ["Threads Sahaja", "Semua Platform (FB, X & Threads)"]:
            platform_tasks.append("- SALINAN THREADS: Gaya perbualan santai / POV tempatan, mencetuskan interaksi komuniti, dan CTA bersahaja.")

        tasks_text = "\n".join(platform_tasks)

        # ---------------------------------------------------------
        # LANGKAH 1: Content Agent (L2) - Mengarang N Variasi
        # ---------------------------------------------------------
        with st.spinner(f"Content Agent sedang mengarang {num_copies} variasi draf iklan..."):
            content_prompt = f"""
            Produk: {selected_product}
            Tema Kempen: {selected_theme}
            Pendekatan Pemasaran: {angle_choice}
            Platform Terlibat: {platform_choice}
            Jumlah Variasi Diperlukan: TEPAT {num_copies} VARIASI BERBEZA

            =======================================================
            SUMBER RUJUKAN 1: FAKTA RASMI & DOKUMEN DATABASE SUPABASE
            =======================================================
            {knowledge_context}

            =======================================================
            SUMBER RUJUKAN 2: STRATEGI KAJIAN PASARAN L1
            =======================================================
            {l1_source_text}

            TUGASAN:
            Hasilkan tepat {num_copies} variasi salinan iklan yang mempunyai sudut 'Hook' dan jalan cerita yang berbeza bagi setiap variasi.
            Asingkan setiap variasi dengan tajuk pemisah yang jelas seperti:
            ### --- VARIASI 1 ---
            ### --- VARIASI 2 ---
            
            Bagi setiap variasi, sertakan platform berikut:
            {tasks_text}
            """

            content_instruction = """
            Awak ialah Senior Direct-Response Copywriter di Malaysia.
            Semua tawaran, harga, ciri produk, dan terma MESTI patuh kepada Dokumen Database.
            Gunakan Bahasa Melayu yang hidup, santai, beremosi, dan relevan dengan budaya tempatan.
            Hanya hasilkan kandungan bagi platform yang diminta.
            """

            draft_text = call_gemini(
                contents=content_prompt,
                system_instruction=content_instruction
            )

        # ---------------------------------------------------------
        # LANGKAH 2: QA & Auto-Correction Agent (L3)
        # ---------------------------------------------------------
        with st.spinner("QA Agent sedang mengaudit fakta & menyediakan versi siap sedia siar..."):
            qa_prompt = f"""
            Produk: {selected_product}
            Peraturan Pematuhan & Fakta Database:
            {knowledge_context}

            Platform Terlibat: {platform_choice}
            Jumlah Variasi: {num_copies} Variasi
            Draf Iklan Asal (L2):
            {draft_text}

            Tugasan QA:
            1. Sediakan Laporan Audit Integriti (Skor 1-10, semakan fakta dokumen, semakan overclaim bagi setiap variasi).
            2. TULIS SEMULA (REWRITE) kesemua {num_copies} variasi di atas menjadi versi yang telah dibaiki 100% (bebas overclaim, nada meyakinkan, format kemas, sedia terus untuk disiarkan).

            Format Output Wajib:
            Tulis laporan audit dahulu, kemudian letakkan pemisah tepat '===REVISED_COPY===' dan sertakan kesemua variasi iklan yang telah dibaiki sepenuhnya selepas pemisah tersebut.
            """

            qa_instruction = """
            Awak ialah Chief Compliance Officer merangkap Senior Editor. 
            Semak draf iklan dengan merujuk ketat kepada Fakta Dokumen Database.
            Pastikan versi REVISED_COPY bebas daripada kesilapan fakta dan sedia untuk terus disiarkan.
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
            "num_copies": num_copies,
            "content_original": draft_text,
            "qa_report": qa_report_text,
            "content_corrected": corrected_copy_text
        })
        st.success(f"Berjaya menjana & mengaudit {num_copies} variasi kandungan!")

    except Exception as e:
        st.error(f"❌ Ralat Penjanaan Kandungan: {str(e)}")

# =========================================================
# 8. PAPARAN ARKIB (3 TAB DENGAN COPY & TELEGRAM)
# =========================================================
if st.session_state.content_history:
    st.markdown("---")
    st.subheader("📂 Arkib Draf Iklan & Salinan Siap Audit")

    for i, item in enumerate(st.session_state.content_history):
        with st.container():
            st.markdown(f"#### 🏷️ #{len(st.session_state.content_history) - i} | [{item['product']}] {item['theme']} ({item.get('num_copies', 1)} Bahan)")
            st.caption(f"📌 Platform: **{item['platform']}** | Gaya: **{item['angle']}**")
            
            tab_final, tab_copy, tab_audit = st.tabs([
                "✨ Salinan Siap Audit (Sedia Siar)",
                "📝 Draf Asal (L2)", 
                "⚖️ Laporan QA & Integriti (L3)"
            ])
            
            with tab_final:
                st.info("💡 Klik ikon salin (copy) di penjuru atas kanan kotak teks di bawah, atau hantar terus ke Telegram.")
                st.code(item["content_corrected"], language=None)
                
                col_act1, col_act2 = st.columns([1.5, 3])
                with col_act1:
                    if st.button("📲 Hantar ke Telegram", key=f"btn_tele_{i}", use_container_width=True):
                        tele_token = st.secrets.get("TELEGRAM_BOT_TOKEN")
                        tele_chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
                        
                        if tele_token and tele_chat_id:
                            tele_text = (
                                f"🚀 *DRAF IKLAN SIAP AUDIT ({item['product']})*\n\n"
                                f"📌 *Tema:* {item['theme']}\n"
                                f"📱 *Platform:* {item['platform']}\n\n"
                                f"{item['content_corrected']}"
                            )
                            res = send_telegram_message(tele_token, tele_chat_id, tele_text)
                            
                            if res.get("ok"):
                                st.success("✅ Berjaya dihantar ke Telegram!")
                            else:
                                st.error(f"Gagal hantar: {res.get('description')}")
                        else:
                            st.warning("⚠️ Sila tetapkan TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID dalam Streamlit Secrets.")

            with tab_copy:
                st.markdown(item["content_original"])

            with tab_audit:
                st.markdown(item["qa_report"])
                
            st.markdown("---")

# =========================================================
# 9. TAHAP 4: STUDIO POSTER UNIVERSAL (CROSS-PLATFORM SINGLE FEED)
# =========================================================
if st.session_state.content_history:
    st.markdown("### 🎨 Tahap 4: Studio Rekaan Poster Universal (Single Feed)")
    st.caption("Jana konsep & blueprint rekaan visual yang sesuai disiarkan di semua media sosial (FB, IG, Threads, X) tanpa terpotong.")

    # Pilih draf iklan daripada arkib untuk dijadikan asas poster
    draft_options = [
        f"#{len(st.session_state.content_history) - idx} - [{item['product']}] {item['theme']} ({item['platform']})"
        for idx, item in enumerate(st.session_state.content_history)
    ]
    selected_draft_idx = st.selectbox("Pilih Salinan Iklan Sebagai Asas Poster:", range(len(draft_options)), format_func=lambda x: draft_options[x])
    target_ad = st.session_state.content_history[selected_draft_idx]

    col_pos_opt1, col_pos_opt2 = st.columns([2, 1])
    with col_pos_opt1:
        st.info("📐 **Piawaian Saiz:** Nisbah **Universal 1:1 (1080 x 1080 px)** atau **Portrait Feed 4:5 (1080 x 1350 px)** dengan kawasan selamat (*Safe Zone*) 10% di setiap penjuru.")
    with col_pos_opt2:
        btn_generate_poster = st.button("Jana Blueprint & Prompt Poster 🖼️", type="primary", use_container_width=True)

    if btn_generate_poster:
        try:
            with st.spinner("Creative Art Director sedang mereka konsep visual universal..."):
                poster_prompt = f"""
                Produk: {target_ad['product']}
                Piawaian Saiz: Universal Single Feed (1080x1080 px / 1:1 atau 1080x1350 px / 4:5)

                =======================================================
                SUMBER 1: FAKTA RASMI & DOKUMEN DATABASE
                =======================================================
                {knowledge_context}

                =======================================================
                SUMBER 2: STRATEGI PSIKOLOGI AVATAR L1
                =======================================================
                {persisted_l1_research if persisted_l1_research else 'Gunakan maklumat teras produk.'}

                =======================================================
                SUMBER 3: SALINAN IKLAN SIAP AUDIT L3
                =======================================================
                {target_ad['content_corrected']}

                Tugasan Creative Director:
                Hasilkan Blueprint Reka Bentuk Poster Pemasaran yang sedia untuk dibuat di Canva / Photoshop, dan prompt imej AI:
                
                1. SUSUN ATUR TEKS POSTER (CANVA-READY):
                   - Hook / Headline Utama: Maksimum 5-6 patah perkataan yang sangat menonjol.
                   - Sub-Headline: 1 ayat padat penerangan nilai / solusi berasaskan dokumen PDF.
                   - Callout Badge / Pakej Tawaran: Pakej harga atau terma penting (contoh: 'Hanya RM30/bln', 'Tawaran Terhad').
                   - Call To Action (CTA): Tindakan segera pada poster (contoh: 'Klik Pautan di Bio' / 'Dapatkan Sekarang').

                2. HIERARKI VISUAL & PALET WARNA:
                   - Skema Warna: 3 kod warna (Primary, Accent, Background) yang sesuai dengan emosi prospek.
                   - Zon Selamat (Safe Zone): Panduan susun atur elemen agar tidak terpotong di feed telefon.

                3. PROMPT GENERASI IMEJ AI (BAHASA INGGERIS):
                   - Tulis 1 prompt berkualiti studio photorealistic / 3D commercial untuk Midjourney, Flux, atau Imagen.
                   - Wajib fokus kepada latar belakang bersih dengan ruang negatif (negative space) untuk meletakkan teks, tanpa teks yang dijana oleh AI.
                """

                poster_instruction = """
                Awak ialah Senior Creative Art Director khusus dalam reka bentuk poster komersial berkonversi tinggi di Malaysia.
                Pastikan teks yang diletakkan pada poster sangat ringkas, padat, dan menepati fakta dokumen rasmi produk.
                """

                poster_result = call_gemini(
                    contents=poster_prompt,
                    system_instruction=poster_instruction
                )

                st.session_state.poster_history.insert(0, {
                    "product": target_ad['product'],
                    "theme": target_ad['theme'],
                    "blueprint": poster_result
                })
                st.success("Blueprint poster berjaya dihasilkan!")

        except Exception as e:
            st.error(f"❌ Ralat Penjanaan Poster: {str(e)}")

    if st.session_state.poster_history:
        st.markdown("---")
        for p_idx, p_item in enumerate(st.session_state.poster_history):
            with st.expander(f"🖼️ Blueprint Poster #{len(st.session_state.poster_history) - p_idx} - [{p_item['product']}] {p_item['theme']}", expanded=(p_idx == 0)):
                st.markdown(p_item["blueprint"])
