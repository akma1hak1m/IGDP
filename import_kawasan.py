# import_kawasan.py
# RUN:
# python manage.py shell
# exec(open("import_kawasan.py").read())

from requests_app.models import Negeri, Daerah, Mukim

# CLEAR OLD DATA
Mukim.objects.all().delete()
Daerah.objects.all().delete()
Negeri.objects.all().delete()

malaysia_data = {

    "JOHOR": {
        "BATU PAHAT": ["Bagan", "Parit Raja", "Sri Gading"],
        "JOHOR BAHRU": ["Tebrau", "Pulai", "Plentong"],
        "KLUANG": ["Kluang", "Machap", "Layang-Layang"],
        "KOTA TINGGI": ["Kota Tinggi", "Ulu Sungai Johor"],
        "KULAI": ["Kulai", "Senai"],
        "MERSING": ["Mersing", "Endau"],
        "MUAR": ["Bandar Maharani", "Bukit Kepong"],
        "PONTIAN": ["Pontian", "Benut"],
        "SEGAMAT": ["Segamat", "Buloh Kasap"],
        "TANGKAK": ["Tangkak", "Bukit Gambir"],
    },

    "KEDAH": {
        "BALING": ["Baling", "Kupang"],
        "BANDAR BAHARU": ["Serdang", "Parit Buntar"],
        "KOTA SETAR": ["Alor Setar", "Kuala Kedah"],
        "KUALA MUDA": ["Sungai Petani", "Merbok"],
        "KUBANG PASU": ["Jitra", "Changlun"],
        "KULIM": ["Kulim", "Lunas"],
        "LANGKAWI": ["Kuah", "Padang Matsirat"],
        "PADANG TERAP": ["Kuala Nerang"],
        "PENDANG": ["Pendang"],
        "POKOK SENA": ["Pokok Sena"],
        "SIK": ["Sik"],
        "YAN": ["Yan", "Gurun"],
    },

    "KELANTAN": {
        "BACHOK": ["Bachok"],
        "GUA MUSANG": ["Gua Musang"],
        "JELI": ["Jeli"],
        "KOTA BHARU": ["Kota Bharu"],
        "KUALA KRAI": ["Kuala Krai"],
        "MACHANG": ["Machang"],
        "PASIR MAS": ["Pasir Mas"],
        "PASIR PUTEH": ["Pasir Puteh"],
        "TANAH MERAH": ["Tanah Merah"],
        "TUMPAT": ["Tumpat"],
    },

    "MELAKA": {
        "ALOR GAJAH": ["Alor Gajah"],
        "JASIN": ["Jasin"],
        "MELAKA TENGAH": ["Ayer Keroh", "Bandar Melaka"],
    },

    "NEGERI SEMBILAN": {
        "JELEBU": ["Kuala Klawang"],
        "JEMPOL": ["Bahau"],
        "KUALA PILAH": ["Kuala Pilah"],
        "PORT DICKSON": ["Port Dickson"],
        "REMBAU": ["Rembau"],
        "SEREMBAN": ["Seremban", "Nilai"],
        "TAMPIN": ["Tampin"],
    },

    "PAHANG": {
        "BENTONG": ["Bentong"],
        "BERA": ["Triang"],
        "CAMERON HIGHLANDS": ["Tanah Rata", "Brinchang"],
        "JERANTUT": ["Jerantut"],
        "KUANTAN": ["Kuantan"],
        "LIPIS": ["Kuala Lipis"],
        "MARAN": ["Maran"],
        "PEKAN": ["Pekan"],
        "RAUB": ["Raub"],
        "ROMPIN": ["Rompin"],
        "TEMERLOH": ["Temerloh"],
    },

    "PERAK": {
        "BAGAN DATUK": ["Bagan Datuk"],
        "BATANG PADANG": ["Tapah"],
        "HILIR PERAK": ["Teluk Intan"],
        "HULU PERAK": ["Gerik"],
        "KAMPAR": ["Kampar"],
        "KERIAN": ["Parit Buntar"],
        "KINTA": ["Ipoh", "Batu Gajah"],
        "KUALA KANGSAR": ["Kuala Kangsar"],
        "LARUT DAN MATANG": ["Taiping", "Kamunting"],
        "MANJUNG": ["Seri Manjung", "Lumut"],
        "MUALLIM": ["Tanjung Malim"],
        "PERAK TENGAH": ["Seri Iskandar"],
        "SELAMA": ["Selama"],
    },

    "PERLIS": {
        "PERLIS": ["Kangar", "Arau", "Padang Besar"],
    },

    "PULAU PINANG": {
        "BARAT DAYA": ["Balik Pulau", "Bayan Lepas"],
        "SEBERANG PERAI SELATAN": ["Nibong Tebal"],
        "SEBERANG PERAI TENGAH": ["Bukit Mertajam"],
        "SEBERANG PERAI UTARA": ["Butterworth", "Kepala Batas"],
        "TIMOR LAUT": ["George Town", "Ayer Itam"],
    },

    "SELANGOR": {
        "GOMBAK": ["Batu Caves", "Rawang"],
        "KLANG": ["Klang", "Meru", "Kapar"],
        "KUALA LANGAT": ["Banting"],
        "KUALA SELANGOR": ["Kuala Selangor"],
        "PETALING": ["Subang Jaya", "Shah Alam", "Petaling Jaya", "Sungai Buloh"],
        "SABAK BERNAM": ["Sabak Bernam"],
        "SEPANG": ["Cyberjaya", "Dengkil", "Salak Tinggi"],
        "ULU LANGAT": ["Kajang", "Cheras", "Semenyih"],
        "ULU SELANGOR": ["Hulu Yam", "Kuala Kubu Bharu"],
    },

    "TERENGGANU": {
        "BESUT": ["Jerteh"],
        "DUNGUN": ["Dungun"],
        "HULU TERENGGANU": ["Kuala Berang"],
        "KEMAMAN": ["Chukai"],
        "KUALA NERUS": ["Gong Badak"],
        "KUALA TERENGGANU": ["Kuala Terengganu"],
        "MARANG": ["Marang"],
        "SETIU": ["Setiu"],
    },

    "WILAYAH PERSEKUTUAN KUALA LUMPUR": {
        "KUALA LUMPUR": ["Cheras", "Setapak", "Wangsa Maju", "Kepong"],
    },

    "WILAYAH PERSEKUTUAN PUTRAJAYA": {
        "PUTRAJAYA": ["Presint 1", "Presint 8", "Presint 15"],
    },

    "SABAH": {
        "KOTA KINABALU": ["Likas", "Inanam"],
        "PENAMPANG": ["Donggongon"],
        "TAWAU": ["Tawau"],
        "SANDAKAN": ["Sandakan"],
        "LAHAD DATU": ["Lahad Datu"],
        "KENINGAU": ["Keningau"],
        "RANAU": ["Ranau"],
    },

    "SARAWAK": {
        "KUCHING": ["Kuching"],
        "MIRI": ["Miri"],
        "SIBU": ["Sibu"],
        "BINTULU": ["Bintulu"],
        "SAMARAHAN": ["Samarahan"],
        "SERIAN": ["Serian"],
        "LIMBANG": ["Limbang"],
    }

}

for negeri_name, daerahs in malaysia_data.items():

    negeri = Negeri.objects.create(nama=negeri_name)

    for daerah_name, mukims in daerahs.items():

        daerah = Daerah.objects.create(
            negeri=negeri,
            nama=daerah_name
        )

        for mukim_name in mukims:

            Mukim.objects.create(
                daerah=daerah,
                nama=mukim_name
            )

print("✅ FULL MALAYSIA kawasan imported successfully")