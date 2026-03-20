import json
import re
import unicodedata

raw_data = """FIREZONE: ULTRA - VÙNG CHIẾN	NETIZEN	ARPG	Fantasy	05/2026	Link
HONKAI: NEXUS ANIMA - TINH LINH GIAO THOA	GAMOTA	Auto Chess	Pokemon	07/2026	Link 
LUDUS: QUYẾT ĐẤU CHIẾN THUẬT	OEG	Card	Fantasy	05/2026	Link
THỦ THÀNH ĐẠI CHIẾN	SKYWAY	Card	Fantasy	05/2026	Link
TA LÀ CAO THỦ VÕ LÂM	JOYGAMES	Card	Kim dung	7/5/2026	Link
CHỦ CÔNG CHẠY ĐI	CMN	Card	Tam Quốc	05/2026	Chưa có
TAM QUỐC 36 KẾ	VTC	Card	Tam Quốc	05/2026	Link
PHONG THẦN TA ĐỊNH ĐOẠT	568	Card	Tây du phong thần	14/03/2026	Link
NA TRA NÁO HẢI	CÔNG TY CỔ PHẦN CÔNG NGHỆ SỐ ALO	Card	Tây du phong thần	18/03/2026	Chưa có
PHI KIẾM TU TIÊN	Velalive	Card	Tu tiên	24/03/2026	Link
CÁ HOÀNG GIA (ROYAL FISH)	ZIE	Chưa rõ	Animal	07/2026	Chưa có
ANH HÙNG TIẾN LÊN	CMN	Chưa rõ	Chưa rõ	07/2026	Chưa có
VŨ TRỤ THẦN THOẠI	CMTECH	Chưa rõ	Chưa rõ	05/2026	Chưa có
NHỊP ĐIỆU THẦN TƯỢNG	CÔNG TY CỔ PHẦN CÔNG NGHỆ SỐ ALO	Chưa rõ	Chưa rõ	05/2026	Chưa có
SKYRIA: ĐẢO KỲ BÍ	GGO	Chưa rõ	Chưa rõ	05/2026	Chưa có
BLOODLINE: DÒNG MÁU ANH HÙNG	GZONE	Chưa rõ	Chưa rõ	07/2026	Chưa có
ĐẠO HỮU XIN DỪNG BƯỚC	JOYGAMES	Chưa rõ	Tu tiên	05/2026	Chưa có
VƯỢT TƯỜNG THÉP	KAN	Chưa rõ	Chưa rõ	05/2026	Chưa có
HÀO KHÍ DU HIỆP	MIGA	Chưa rõ	Chưa rõ	05/2026	Chưa có
CƠ GIỚI CHIẾN	SKYWAY	Chưa rõ	Chưa rõ	05/2026	Chưa có
GIANG HỒ KỲ NGỘ	VPLAY	Chưa rõ	Chưa rõ	05/2026	Chưa có
BỬU BỐI TRUYỀN KỲ	CMN	Chưa rõ	Pokemon	05/2026	Chưa có
ANH KIỆT TAM QUỐC	CMN	Chưa rõ	Tam Quốc	07/2026	Chưa có
VẤN ĐỈNH TAM QUỐC	SOHA	Chưa rõ	Tam Quốc	05/2026	Chưa có
THẦN MA ARENA	CMN	MMO	Fantasy	05/2026	Chưa có
KIẾM VŨ SƠN HÀ	 Broga	MMO	Kiếm hiệp	05/2026	Chưa có
HOÀN MỸ TAM QUỐC	VGP	MMO	Tam Quốc	05/2026	Chưa có
VÕ HIỆP ORIGIN	FunGames 	MMO	Võ hiệp	05/2026	Link
Thợ Săn Siêu Cấp	VGP	MMO	Fantasy	13/05/2026	Link
THẾ GIỚI HOA VIÊN CỦA TÔI	Vision	RPG	Cổ trang	05/2026	Link
BALLISTIC HERO VNG	VNG	Shooter	Fantasy	10/4/2026	Link
MÈO MÁY SIÊU QUẤY	DRAGON GAME	Side Scrolling	Anime	3/2026	Chưa có
TRUYỀN THUYẾT HAKI	EPICGOLD	Side Scrolling	Anime	Q4/2026	Link
RỒNG THẦN ONLINE	TEPAYLINK	Side Scrolling	Anime	05/2026	Chưa có
NẤM ĐẠI CHIẾN	TEPAYLINK	Side Scrolling	Fantasy	05/2026	Chưa có
Tomb Busters	Giant Network	Survival co-op	Fantasy	27/05/2026	Link
QUÁI THÚ PHÒNG THỦ	OEG	TD	Fantasy	05/2026	Chưa có
TOTAL FOOTBALL VNG	VNG	Thể thao	Sports	05/2026	Link
ĐẾ CHẾ BÓNG ĐÁ	WEPLAY	Thể Thao	Sports	05/2026	Chưa có"""

def slugify(text):
    text = str(text).lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text

def parse_date(date_str):
    d = date_str.strip()
    
    # 13/05/2026 format
    m1 = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', d)
    if m1:
        day = int(m1.group(1))
        month = int(m1.group(2))
        year = int(m1.group(3))
        return f"{day:02d}-{month:02d}-{year} 08:00", False
    
    # 05/2026 or 3/2026
    m2 = re.match(r'^(\d{1,2})/(\d{4})$', d)
    if m2:
        month = int(m2.group(1))
        year = int(m2.group(2))
        return f"01-{month:02d}-{year} 00:00", True
        
    # Q4/2026 or similar
    m3 = re.match(r'^Q(\d)/(\d{4})$', d, re.IGNORECASE)
    if m3:
        q = int(m3.group(1))
        year = int(m3.group(2))
        month = (q-1)*3 + 1
        return f"01-{month:02d}-{year} 00:00", True

    return d + " 00:00", True

def main():
    try:
        with open('e:/ProjectAI/Project_alert_gov/afkmobi_data.json', 'r', encoding='utf-8') as f:
            existing_games = json.load(f)
    except Exception as e:
        existing_games = []
        
    existing_ids = {g.get('id'): g for g in existing_games if g.get('id')}
    new_count = 0
    updated_count = 0
    
    lines = [L for L in raw_data.split('\n') if L.strip("\r\n\t ")]
    for line in lines:
        parts = line.split('\t')
        if len(parts) >= 2:
            name = parts[0].strip()
            publisher = parts[1].strip()
            genre = parts[2].strip() if len(parts) > 2 else ""
            theme = parts[3].strip() if len(parts) > 3 else ""
            date_raw = parts[4].strip() if len(parts) > 4 else ""
            link_raw = parts[5].strip() if len(parts) > 5 else ""
            
            slug = slugify(name)
            
            genre_parts = []
            if genre and genre.lower() != "chưa rõ":
                genre_parts.append(f"Thể loại: {genre}")
            if theme and theme.lower() != "chưa rõ":
                genre_parts.append(f"Theme: {theme}")
            if publisher and publisher.lower() != "chưa rõ":
                genre_parts.append(f"NPH: {publisher}")
            
            genre_str = ". ".join(genre_parts) + "." if genre_parts else ""
            
            formatted_date, is_approx = parse_date(date_raw)
            url = link_raw if link_raw.lower() not in ("chưa có", "link", "") else ""
            
            # Match afkmobi formatting
            tags = []
            if formatted_date:
                tags.append(date_raw)
            tags.extend(["REG", "OBT"])
            
            game = {
                "id": slug,
                "name": name,
                "genre": genre_str,
                "release_date": formatted_date,
                "is_approximate": is_approx,
                "status_tags": tags,
                "url": url,
                "image": ""
            }
            
            if slug not in existing_ids:
                existing_games.insert(0, game)
                existing_ids[slug] = game
                new_count += 1
            else:
                # Update existing only if they miss info? 
                # Let's just merge missing fields
                ex = existing_ids[slug]
                if not ex.get('genre') and game['genre']:
                    ex['genre'] = game['genre']
                    updated_count += 1
                elif game['url'] and not ex.get('url'):
                    ex['url'] = game['url']
                    updated_count += 1
                
    with open('e:/ProjectAI/Project_alert_gov/afkmobi_data.json', 'w', encoding='utf-8') as f:
        json.dump(existing_games, f, indent=2, ensure_ascii=False)
        
    print(f"Added {new_count} new games. Updated {updated_count} existing games.")

if __name__ == '__main__':
    main()
