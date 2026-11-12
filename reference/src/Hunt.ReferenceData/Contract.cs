namespace HuntBriefing.ReferenceData;
internal static class Contract {
 internal static readonly Dictionary<string,Dictionary<string,string>> Fields=new() {
["weapons"] = new() {["nameEn"]="text",["nameKo"]="text",["variantOfId"]="id",["ammoClass"]="text",["priceHuntDollars"]="int",["damage"]="number",["velocityMps"]="number",["dropMeters"]="number",["cycleSeconds"]="number",["slots"]="int",["capacity"]="int",["reserveAmmo"]="int",["reloadSeconds"]="number",["customAmmoIds"]="ids",["customAmmoCoverage"]="text",["unlockCondition"]="text",["imageAssetId"]="id"},
["ammo"] = new() {["nameEn"]="text",["weaponId"]="id",["priceHuntDollars"]="int",["slots"]="int",["damage"]="number",["velocityMps"]="number",["dropMeters"]="number",["effects"]="text",["imageAssetId"]="id"},
["gear"] = new() {["nameEn"]="text",["nameKo"]="text",["kind"]="text",["priceHuntDollars"]="int",["packCount"]="int",["effect"]="text",["durationSeconds"]="number",["damage"]="number",["rangeMeters"]="number",["unlockCondition"]="text",["lightStamina"]="number",["heavyStamina"]="number",["lightDamage"]="number",["heavyDamage"]="number",["reachMeters"]="number",["imageAssetId"]="id"},
["traits"] = new() {["nameEn"]="text",["nameKo"]="text",["category"]="text",["costPoints"]="int",["acquisition"]="texts",["flags"]="texts",["effectKo"]="text",["effectStructured"]="object",["conditions"]="text",["equipmentIds"]="ids",["imageAssetId"]="id"},
["skins"] = new() {["nameEn"]="text",["nameKo"]="text",["kind"]="text",["baseItemId"]="id",["baseItemName"]="text",["releaseDate"]="text",["acquisition"]="text",["availability"]="text",["eventOrDlc"]="text",["imageAssetId"]="id"},
["images"] = new() {["nameEn"]="text",["relatedId"]="id",["candidateUrl"]="url",["licenseStatus"]="text",["redistributionApproved"]="bool",["localFile"]="text",["sha256"]="text",["licenseEvidenceUrl"]="url",["attribution"]="text"},
};
 internal static readonly Dictionary<string,string[]> Required=new() {
["weapons"] = ["nameEn","ammoClass","priceHuntDollars","damage","velocityMps","dropMeters","cycleSeconds","slots","customAmmoCoverage"],
["ammo"] = ["nameEn","weaponId","priceHuntDollars","slots","damage","velocityMps","dropMeters","effects"],
["gear"] = ["nameEn","kind","priceHuntDollars","packCount","effect","unlockCondition"],
["traits"] = ["nameEn","category","costPoints","acquisition","flags","effectKo","conditions"],
["skins"] = ["nameEn","kind","baseItemName","releaseDate","acquisition","availability","eventOrDlc"],
["images"] = ["nameEn","relatedId","licenseStatus","redistributionApproved","localFile","sha256","licenseEvidenceUrl","attribution"],
};
}
