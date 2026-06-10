import geopandas as gpd

from requests_app.models import Negeri, Daerah, Mukim

# =========================
# CLEAR OLD DATA
# =========================
Mukim.objects.all().delete()
Daerah.objects.all().delete()
Negeri.objects.all().delete()

# =========================
# IMPORT NEGERI
# =========================
state_gdf = gpd.read_file(
    r"D:\KIRIJA\MYSA\DATA GEOSPATIAL BERSEPADU MYSA\system\gadm41_MYS_shp\gadm41_MYS_0.shp"
)

for _, row in state_gdf.iterrows():

    Negeri.objects.get_or_create(
        nama=row["NAME_1"]
    )

print("NEGERI IMPORTED")


# =========================
# IMPORT DAERAH
# =========================
district_gdf = gpd.read_file(
    r"D:\KIRIJA\MYSA\DATA GEOSPATIAL BERSEPADU MYSA\system\gadm41_MYS_shp\gadm41_MYS_1.shp"
)

for _, row in district_gdf.iterrows():

    negeri = Negeri.objects.filter(
        nama=row["NAME_1"]
    ).first()

    if negeri:

        Daerah.objects.get_or_create(
            nama=row["NAME_2"],
            negeri=negeri
        )

print("DAERAH IMPORTED")


# =========================
# IMPORT MUKIM
# =========================
mukim_gdf = gpd.read_file(
    r"D:\KIRIJA\MYSA\DATA GEOSPATIAL BERSEPADU MYSA\system\gadm41_MYS_shp\gadm41_MYS_2.shp"
)

for _, row in mukim_gdf.iterrows():

    daerah = Daerah.objects.filter(
        nama=row["NAME_2"]
    ).first()

    if daerah:

        Mukim.objects.get_or_create(
            nama=row["NAME_3"],
            daerah=daerah
        )

print("MUKIM IMPORTED")

print("DONE ALL IMPORT")