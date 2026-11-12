using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace HuntBriefing.ReferenceData;
public enum ReferenceMode { Disabled, Shadow, ReadOnly }
public sealed record ReferenceOptions
{
    public ReferenceMode Mode { get; init; } = ReferenceMode.Disabled;
    public bool AllowAiContext { get; init; } = false;
    public Uri? ManifestUrl { get; init; }
    public string TrustedPublicKeyPem { get; init; } = "";
    public string? CacheDirectory { get; init; }
    public TimeSpan Timeout { get; init; } = TimeSpan.FromSeconds(4);
    public TimeSpan MaxCacheAge { get; init; } = TimeSpan.FromDays(30);
}
public sealed record ReferenceStatus(string State, bool HasVerifiedCache, string? Version);
/// <summary>Independent opt-in reader. No UI, feed writer, push sender, image loader or scheduler.</summary>
public sealed class ReferenceCatalogClient : IDisposable
{
    private readonly ReferenceOptions options;
    private readonly HttpClient http;
    private readonly SemaphoreSlim gate = new(1,1);
    private Cache? current;
    private bool diskAttempted;
    private readonly Action<ReferenceStatus>? observe;
    private sealed record Cache(byte[] Envelope, byte[] Catalog, DateTimeOffset StoredAt, string Version);
    private sealed record DiskCache(string Origin, string Envelope, string Catalog, DateTimeOffset StoredAt);
    private static readonly string[] Domains = ["weapons","ammo","gear","traits","skins","images"];
    public ReferenceCatalogClient(ReferenceOptions? options = null, Action<ReferenceStatus>? observer = null)
        : this(options ?? new(),new HttpClientHandler { AllowAutoRedirect=false, AutomaticDecompression=DecompressionMethods.None },observer) { }
    // Test seam. Production constructor always disables redirects.
    public ReferenceCatalogClient(ReferenceOptions options, HttpMessageHandler handler, Action<ReferenceStatus>? observer = null)
    {
        this.options=options; observe=observer;
        http=new HttpClient(handler) { Timeout=System.Threading.Timeout.InfiniteTimeSpan };
    }
    public async Task<ReferenceStatus> RefreshAsync(CancellationToken cancellationToken=default)
    {
        // Disabled means no HTTP, no disk reads and no reference data exposure.
        if(options.Mode==ReferenceMode.Disabled)return new("disabled",false,null);
        if(!Enum.IsDefined(options.Mode) || !SafeEndpoint(options.ManifestUrl) || string.IsNullOrWhiteSpace(options.TrustedPublicKeyPem) ||
            options.Timeout<=TimeSpan.Zero || options.Timeout>TimeSpan.FromSeconds(10))return Status("unconfigured");
        using var timeout=CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(options.Timeout);
        bool entered=false;
        try
        {
            await gate.WaitAsync(timeout.Token).ConfigureAwait(false);entered=true;
            if(!diskAttempted){diskAttempted=true;await RestoreAsync(timeout.Token).ConfigureAwait(false);}
            byte[] envelope=await DownloadAsync(options.ManifestUrl!,65536,timeout.Token).ConfigureAwait(false);
            using var manifest=VerifyManifest(envelope);
            var m=manifest.RootElement;
            var url=new Uri(options.ManifestUrl!,m.GetProperty("catalogRelativePath").GetString());
            if(url.GetLeftPart(UriPartial.Authority)!=options.ManifestUrl!.GetLeftPart(UriPartial.Authority) || !url.AbsolutePath.StartsWith(new Uri(options.ManifestUrl!,".").AbsolutePath,StringComparison.Ordinal))throw new InvalidDataException("path");
            byte[] catalog=await DownloadAsync(url,8_000_000,timeout.Token).ConfigureAwait(false);
            ValidateSnapshot(m,catalog);
            var next=new Cache(envelope,catalog,DateTimeOffset.UtcNow,m.GetProperty("version").GetString()!);
            // A disk-write failure retains the previous good cache; no partial commit.
            await PersistAsync(next,timeout.Token).ConfigureAwait(false);
            Volatile.Write(ref current,next);
            return Status(options.Mode==ReferenceMode.Shadow?"shadow_verified":"updated");
        }
        catch(Exception e) when(e is not OutOfMemoryException and not StackOverflowException)
        { return Status(e is OperationCanceledException or TimeoutException?"timeout_or_cancelled":"reference_unavailable"); }
        finally{if(entered)gate.Release();}
    }
    // Explicit, separate context gate; shadow mode cannot return game data.
    public JsonElement? FindVerified(string domain,string exactName)
    {
        if(options.Mode!=ReferenceMode.ReadOnly || !options.AllowAiContext || domain=="images" || !Domains.Contains(domain))return null;
        var cached=UsableCache();if(cached is null)return null;
        using var doc=Parse(cached.Catalog);
        var matches=doc.RootElement.GetProperty(domain).EnumerateArray().Where(x=>string.Equals(x.GetProperty("values").GetProperty("nameEn").GetString(),exactName,StringComparison.OrdinalIgnoreCase)).ToArray();
        // Ambiguous variant names are never guessed.
        return matches.Length==1?matches[0].Clone():null;
    }
    private Cache? UsableCache()
    {
        var c=Volatile.Read(ref current);var age=c is null?TimeSpan.MaxValue:DateTimeOffset.UtcNow-c.StoredAt;
        return c is not null && age>=TimeSpan.Zero && age<=options.MaxCacheAge?c:null;
    }
    private ReferenceStatus Status(string state)
    {
        var c=UsableCache();var status=new ReferenceStatus(state,c is not null,c?.Version);
        try{observe?.Invoke(status);}catch{ /* An optional observer cannot break publication/UI. */ }
        return status;
    }
    private static bool SafeEndpoint(Uri? uri)=>uri is not null && uri.IsAbsoluteUri && uri.Scheme==Uri.UriSchemeHttps &&
        uri.UserInfo.Length==0 && uri.Query.Length==0 && uri.Fragment.Length==0 &&
        uri.AbsolutePath.EndsWith("/reference/catalog/v1/active.json",StringComparison.Ordinal) && !uri.OriginalString.Contains('%') && !uri.OriginalString.Contains('\\');
    private async Task<byte[]> DownloadAsync(Uri uri,int limit,CancellationToken token)
    {
        using var response=await http.GetAsync(uri,HttpCompletionOption.ResponseHeadersRead,token).WaitAsync(token).ConfigureAwait(false);
        if((int)response.StatusCode is >=300 and <400)throw new InvalidDataException("redirect");
        response.EnsureSuccessStatusCode();
        if(response.RequestMessage?.RequestUri is Uri actual && actual!=uri)throw new InvalidDataException("redirect origin");
        if(response.Content.Headers.ContentLength>limit)throw new InvalidDataException("size");
        await using var input=await response.Content.ReadAsStreamAsync(token).ConfigureAwait(false);
        using var output=new MemoryStream();byte[] buffer=new byte[16384];int n;
        while((n=await input.ReadAsync(buffer,token).AsTask().WaitAsync(token).ConfigureAwait(false))!=0)
        {if(output.Length+n>limit)throw new InvalidDataException("size");output.Write(buffer,0,n);}
        if(output.Length==0)throw new InvalidDataException("empty");return output.ToArray();
    }
    private JsonDocument VerifyManifest(byte[] envelope)
    {
        using var wrapper=Parse(envelope);var e=wrapper.RootElement;
        ExactKeys(e,["algorithm","payload","signature"]);
        if(e.GetProperty("algorithm").GetString()!="ECDSA-P256-SHA256-DER")throw new InvalidDataException("signature algorithm");
        byte[] payload=Convert.FromBase64String(e.GetProperty("payload").GetString()!),signature=Convert.FromBase64String(e.GetProperty("signature").GetString()!);
        using var key=ECDsa.Create();key.ImportFromPem(options.TrustedPublicKeyPem);
        if(key.KeySize!=256 || !key.VerifyData(payload,signature,HashAlgorithmName.SHA256,DSASignatureFormat.Rfc3279DerSequence))throw new InvalidDataException("signature");
        var doc=Parse(payload);
        try
        {
            var m=doc.RootElement;ExactKeys(m,["schemaVersion","version","snapshotId","published","researchOnly","contentSha256","catalogRelativePath","counts"]);
            if(m.GetProperty("schemaVersion").GetString()!="1.0.0" || !m.GetProperty("published").GetBoolean() || m.GetProperty("researchOnly").GetBoolean())throw new InvalidDataException("draft/schema");
            string hash=m.GetProperty("contentSha256").GetString()!;
            if(!Regex.IsMatch(hash,"^[a-f0-9]{64}$") || m.GetProperty("catalogRelativePath").GetString()!="snapshots/"+hash+".json")throw new InvalidDataException("path/hash");
            if(!Regex.IsMatch(m.GetProperty("version").GetString()!,"^[0-9]+\\.[0-9]+\\.[0-9]+$"))throw new InvalidDataException("version");
            ExactKeys(m.GetProperty("counts"),Domains);return doc;
        }catch{doc.Dispose();throw;}
    }
    private static void ValidateSnapshot(JsonElement manifest,byte[] bytes)
    {
        if(!string.Equals(Convert.ToHexString(SHA256.HashData(bytes)),manifest.GetProperty("contentSha256").GetString(),StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("checksum");
        using var doc=Parse(bytes);var root=doc.RootElement;
        ExactKeys(root,["schemaVersion","snapshotId","dataVersion","sourcePatch","generatedAt","researchOnly","published",..Domains]);
        if(root.GetProperty("schemaVersion").GetString()!="1.0.0" || root.GetProperty("researchOnly").GetBoolean() || !root.GetProperty("published").GetBoolean() ||
            root.GetProperty("dataVersion").GetString()!=manifest.GetProperty("version").GetString() || root.GetProperty("snapshotId").GetString()!=manifest.GetProperty("snapshotId").GetString())throw new InvalidDataException("snapshot metadata");
        var ids=new Dictionary<string,string>();
        foreach(var domain in Domains)
        {
            var array=root.GetProperty(domain);if(array.ValueKind!=JsonValueKind.Array || array.GetArrayLength()>20000 || array.GetArrayLength()!=manifest.GetProperty("counts").GetProperty(domain).GetInt32() || (domain is "weapons" or "gear" or "traits" && array.GetArrayLength()==0))throw new InvalidDataException("count");
            var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach(var item in array.EnumerateArray())
            {
                ExactKeys(item,["id","values","fieldReviews"]);string id=item.GetProperty("id").GetString()!;
                if(!Regex.IsMatch(id,"^[a-z][a-z0-9-]+$") || !ids.TryAdd(id,domain))throw new InvalidDataException("duplicate ID");
                var values=item.GetProperty("values");
                string NamePart(string f)=>values.TryGetProperty(f,out var value)?value.ToString():"";
                if(!names.Add(NamePart("nameEn")+"|"+NamePart("baseItemId")+"|"+NamePart("weaponId")))throw new InvalidDataException("duplicate name");
                var reviews=item.GetProperty("fieldReviews");ExactKeys(values,Contract.Fields[domain].Keys);ExactKeys(reviews,Contract.Fields[domain].Keys);
                if(values.GetProperty("nameEn").ValueKind!=JsonValueKind.String || string.IsNullOrWhiteSpace(values.GetProperty("nameEn").GetString()))throw new InvalidDataException("name");
                foreach(var (field,type) in Contract.Fields[domain])
                {
                    var value=values.GetProperty(field);var review=reviews.GetProperty(field);ExactKeys(review,["status","sourceId","sourceUrl","observedAt","sourcePatch","evidenceId"]);
                    string status=review.GetProperty("status").GetString()!;
                    if(value.ValueKind==JsonValueKind.Null)
                    {if(status is not ("missing" or "not_applicable") || (Contract.Required[domain].Contains(field) && status!="not_applicable"))throw new InvalidDataException("null review");}
                    else if(status!="verified" || !ValidValue(value,type))throw new InvalidDataException("unverified/type");
                    if(status is "verified" or "not_applicable")foreach(var key in new[]{"sourceId","sourceUrl","observedAt","evidenceId"})if(string.IsNullOrWhiteSpace(review.GetProperty(key).GetString()))throw new InvalidDataException("evidence");
                }
                if(domain=="weapons" && values.GetProperty("customAmmoCoverage").GetString() is not ("complete" or "none"))throw new InvalidDataException("ammo survey");
                if(domain=="images" && (!values.GetProperty("redistributionApproved").GetBoolean() || values.GetProperty("licenseStatus").GetString()!="approved" || !Regex.IsMatch(values.GetProperty("localFile").GetString()??"","^assets/[a-f0-9]{64}\\.webp$")))throw new InvalidDataException("image rights");
            }
        }
        var records=Domains.SelectMany(d=>root.GetProperty(d).EnumerateArray()).ToDictionary(i=>i.GetProperty("id").GetString()!);
        foreach(var domain in Domains)foreach(var item in root.GetProperty(domain).EnumerateArray())foreach(var value in item.GetProperty("values").EnumerateObject())
        {
            string? target=value.Name switch { "variantOfId" or "weaponId"=>"weapons", "imageAssetId"=>"images", "customAmmoIds"=>"ammo", _=>null };
            void CheckLink(string link)
            {
                if(!ids.TryGetValue(link,out var actual) || (target is not null && actual!=target))throw new InvalidDataException("relation");
                if(value.Name=="customAmmoIds" && records[link].GetProperty("values").GetProperty("weaponId").GetString()!=item.GetProperty("id").GetString())throw new InvalidDataException("ammo owner");
            }
            if(value.Name.EndsWith("Ids",StringComparison.Ordinal) && value.Value.ValueKind==JsonValueKind.Array)
            {var links=value.Value.EnumerateArray().Select(x=>x.GetString()!).ToArray();if(links.Distinct().Count()!=links.Length)throw new InvalidDataException("duplicate relation");foreach(var link in links)CheckLink(link);}
            else if(value.Name.EndsWith("Id",StringComparison.Ordinal) && value.Value.ValueKind==JsonValueKind.String)CheckLink(value.Value.GetString()!);
        }
        foreach(var ammo in root.GetProperty("ammo").EnumerateArray())
        {
            var weapon=records[ammo.GetProperty("values").GetProperty("weaponId").GetString()!];
            var links=weapon.GetProperty("values").GetProperty("customAmmoIds");
            if(links.ValueKind!=JsonValueKind.Array || !links.EnumerateArray().Any(x=>x.GetString()==ammo.GetProperty("id").GetString()))throw new InvalidDataException("ammo reciprocity");
        }
    }
    private static bool ValidValue(JsonElement v,string type)=>type switch
    {
        "int"=>v.ValueKind==JsonValueKind.Number && v.TryGetInt64(out long n) && n>=0,
        "number"=>v.ValueKind==JsonValueKind.Number && v.TryGetDouble(out double n) && double.IsFinite(n) && n>=0,
        "bool"=>v.ValueKind is JsonValueKind.True or JsonValueKind.False,
        "ids" or "texts"=>v.ValueKind==JsonValueKind.Array && v.EnumerateArray().All(x=>x.ValueKind==JsonValueKind.String),
        "object"=>v.ValueKind==JsonValueKind.Object,
        _=>v.ValueKind==JsonValueKind.String && !string.IsNullOrEmpty(v.GetString())
    };
    private static JsonDocument Parse(byte[] bytes)
    {
        var doc=JsonDocument.Parse(bytes,new JsonDocumentOptions{MaxDepth=40});
        try{RejectDuplicateKeys(doc.RootElement);return doc;}catch{doc.Dispose();throw;}
    }
    private static void RejectDuplicateKeys(JsonElement e)
    {
        if(e.ValueKind==JsonValueKind.Object){var names=new HashSet<string>();foreach(var p in e.EnumerateObject()){if(!names.Add(p.Name))throw new InvalidDataException("duplicate key");RejectDuplicateKeys(p.Value);}}
        else if(e.ValueKind==JsonValueKind.Array)foreach(var x in e.EnumerateArray())RejectDuplicateKeys(x);
    }
    private static void ExactKeys(JsonElement e,IEnumerable<string> expected)
    {if(e.ValueKind!=JsonValueKind.Object || !e.EnumerateObject().Select(x=>x.Name).ToHashSet().SetEquals(expected))throw new InvalidDataException("schema keys");}
    private string? CachePath=>options.CacheDirectory is null?null:Path.Combine(options.CacheDirectory,"hunt-reference-v1.cache.json");
    private async Task RestoreAsync(CancellationToken token)
    {
        try
        {
            var path=CachePath;if(path is null || !File.Exists(path) || new FileInfo(path).Length>11_000_000)return;
            byte[] data=await File.ReadAllBytesAsync(path,token).ConfigureAwait(false);using var parsed=Parse(data);
            var disk=JsonSerializer.Deserialize<DiskCache>(data)!;
            if(disk.Origin!=options.ManifestUrl!.AbsoluteUri || DateTimeOffset.UtcNow-disk.StoredAt<TimeSpan.Zero || DateTimeOffset.UtcNow-disk.StoredAt>options.MaxCacheAge)return;
            byte[] envelope=Convert.FromBase64String(disk.Envelope),catalog=Convert.FromBase64String(disk.Catalog);
            using var manifest=VerifyManifest(envelope);ValidateSnapshot(manifest.RootElement,catalog);
            Volatile.Write(ref current,new Cache(envelope,catalog,disk.StoredAt,manifest.RootElement.GetProperty("version").GetString()!));
        }catch(Exception e) when(e is not OutOfMemoryException and not StackOverflowException){ /* Corrupt cache is ignored. */ }
    }
    private async Task PersistAsync(Cache next,CancellationToken token)
    {
        var path=CachePath;if(path is null)return;Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string tmp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try
        {
            var disk=new DiskCache(options.ManifestUrl!.AbsoluteUri,Convert.ToBase64String(next.Envelope),Convert.ToBase64String(next.Catalog),next.StoredAt);
            await File.WriteAllBytesAsync(tmp,JsonSerializer.SerializeToUtf8Bytes(disk),token).ConfigureAwait(false);
            token.ThrowIfCancellationRequested();File.Move(tmp,path,true);
        }finally{try{File.Delete(tmp);}catch(IOException){}}
    }
    public void Dispose(){http.Dispose();gate.Dispose();}
}
