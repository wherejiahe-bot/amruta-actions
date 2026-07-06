"""
Step 2: Extract matching Chinese paragraphs from official translation document.
The English content from API matches the latter portion of 1981-07-05 导师普祭.md
Extract the corresponding Chinese paragraphs and build alignment pairs.
"""
import json, re, os

# Read article_raw.json
with open('article_raw.json', 'r', encoding='utf-8') as f:
    article = json.load(f)

en_content = article['content']
en_title = article['title']
en_date = article['date']
en_link = article['link']

print(f"English title: {en_title}")
print(f"English date: {en_date}")
print(f"English content length: {len(en_content)}")

# Read the official Chinese document
doc_path = r'F:\霎哈嘉瑜伽\sahaja live talks\1981-07-05 导师普祭.md'
with open(doc_path, 'r', encoding='utf-8') as f:
    doc_content = f.read()

# Extract frontmatter
fm_match = re.match(r'^---\n(.*?)\n---\n(.*)', doc_content, re.DOTALL)
if fm_match:
    fm_text = fm_match.group(1)
    body = fm_match.group(2)
else:
    body = doc_content
    fm_text = ""

# Parse frontmatter fields
fm_dict = {}
for line in fm_text.strip().split('\n'):
    m = re.match(r'^(\w+):\s*"?(.*?)"?\s*$', line)
    if m:
        fm_dict[m.group(1)] = m.group(2).strip()

cn_source = fm_dict.get('source', '')
cn_title_fm = fm_dict.get('title', '')
print(f"Chinese doc title: {cn_title_fm}")
print(f"Chinese doc source: {cn_source}")

# Split body into alternating EN/CN paragraphs
# Pattern: English paragraph followed by Chinese paragraph
lines = body.strip().split('\n')

# Separate EN and CN paragraphs
# Lines with Chinese chars are CN, lines without are EN
en_paragraphs = []
cn_paragraphs = []

# First, identify the EN/CN alternation pattern
# Looking at the file: EN para, CN para, EN para, CN para...
current_en = []
current_cn = []
in_en = True

for line in lines:
    # Skip header lines
    if line.startswith('Cambridge') or line.startswith('---') or line.strip() == '':
        continue
    
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', line))
    
    if has_chinese:
        if current_en:
            en_paragraphs.append(' '.join(current_en))
            current_en = []
        current_cn.append(line)
    else:
        if current_cn:
            cn_paragraphs.append(' '.join(current_cn))
            current_cn = []
        current_en.append(line)

if current_en:
    en_paragraphs.append(' '.join(current_en))
if current_cn:
    cn_paragraphs.append(' '.join(' '.join(current_cn)))

print(f"\nFound {len(en_paragraphs)} EN paragraphs, {len(cn_paragraphs)} CN paragraphs")

# Find which CN paragraphs correspond to the API content
# The API content starts with "Only sometimes I find a conflict..."
# Search for the matching EN paragraphs in the document
en_api_clean = en_content.strip()

# Find matching segments
# The API content is roughly the last few EN paragraphs of the doc
# Let's find the index by searching for key phrases

# Key phrase from API content
key_phrases = [
    "Only sometimes I find a conflict",
    "Your priority should be sahaja yoga",
    "she should not give way",
    "no individualistic efforts",
    "I see that spirit in you"
]

# Find which EN paragraphs contain these key phrases
matching_en_indices = []
for i, para in enumerate(en_paragraphs):
    for phrase in key_phrases:
        if phrase.lower() in para.lower():
            matching_en_indices.append(i)
            break

print(f"Matching EN paragraph indices: {matching_en_indices}")

# The CN paragraphs that correspond are at the same indices (EN[i] <-> CN[i])
# But need to check alignment
pairs = []
for idx in matching_en_indices:
    if idx < len(cn_paragraphs):
        en_para = en_paragraphs[idx].strip()
        cn_para = cn_paragraphs[idx].strip()
        
        # Verify: API content should be in this EN paragraph
        if en_para and cn_para:
            pairs.append({
                'index': idx,
                'en': en_para,
                'cn': cn_para
            })

print(f"\nBuilt {len(pairs)} pairs")

# Verify API content is preserved exactly
all_en_in_pairs = '\n'.join([p['en'] for p in pairs])
api_content_normalized = re.sub(r'\s+', ' ', en_api_clean).strip()
pairs_content_normalized = re.sub(r'\s+', ' ', all_en_in_pairs).strip()

print(f"\nAPI content normalized length: {len(api_content_normalized)}")
print(f"Pairs EN content normalized length: {len(pairs_content_normalized)}")

# Check if API content is a substring of pairs content
if api_content_normalized in pairs_content_normalized or pairs_content_normalized in api_content_normalized:
    print("✅ Content match verified")
else:
    # Try more flexible matching
    print("⚠️ Content not exact match, checking overlap...")
    overlap = sum(1 for a, b in zip(api_content_normalized, pairs_content_normalized) if a == b)
    print(f"Overlap: {overlap}/{len(api_content_normalized)} chars")

# Build output
output = {
    'date': en_date,
    'title': en_title,
    'source': cn_source,
    'pairs': pairs,
    'full_en': en_content,
    'full_cn_doc': cn_title_fm,
    'num_pairs': len(pairs)
}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pairs.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ Step2: Saved {len(pairs)} pairs to pairs.json")
for i, p in enumerate(pairs):
    print(f"  Pair {i+1}: EN={len(p['en'])} chars, CN={len(p['cn'])} chars")
