using System.Net;
using System.Text;
using HuntBriefing.ReferenceData;

var fixture=Path.GetFullPath(args[0]);var temp=Path.Combine(Path.GetTempPath(),"hunt-reference-tests-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(temp);
int passed=0;
void Check(bool condition,string name){if(!condition)throw new Exception("FAIL: "+name);Console.WriteLine("PASS: "+name);passed++;}
ReferenceOptions Options(ReferenceMode mode=ReferenceMode.Shadow,bool context=false,string? cache=null)=>new(){Mode=mode,AllowAiContext=context,ManifestUrl=new("https://example.invalid/reference/catalog/v1/active.json"),TrustedPublicKeyPem=File.ReadAllText(Path.Combine(fixture,"public.pem")),Timeout=TimeSpan.FromMilliseconds(100),CacheDirectory=cache};
try
{
    var h=new Fake(fixture);using(var c=new ReferenceCatalogClient(new(),h))Check((await c.RefreshAsync()).State=="disabled" && h.Calls==0 && c.FindVerified("weapons","TEST ONLY weapons") is null,"default disabled: zero network/data exposure");
    h=new Fake(fixture);using(var c=new ReferenceCatalogClient(Options(),h))Check((await c.RefreshAsync()).State=="shadow_verified" && c.FindVerified("weapons","TEST ONLY weapons") is null,"shadow validates without AI context");
    h=new Fake(fixture);using(var c=new ReferenceCatalogClient(Options(ReferenceMode.ReadOnly),h)){await c.RefreshAsync();Check(c.FindVerified("weapons","TEST ONLY weapons") is null,"second AI context gate");}
    h=new Fake(fixture);using(var c=new ReferenceCatalogClient(Options(ReferenceMode.ReadOnly,true,temp),h))
    {
        Check((await c.RefreshAsync()).State=="updated" && c.FindVerified("weapons","TEST ONLY weapons") is not null,"explicit read-only context + durable cache");
        foreach(var fail in new[]{"dns","500","timeout","empty","missing","unverified","draft","hash","signature","path","redirect","wrongrelation"})
        {
            h.Mode=fail;var status=await c.RefreshAsync();Check(status.State is "reference_unavailable" or "timeout_or_cancelled" && status.HasVerifiedCache && status.Version=="1.0.0" && c.FindVerified("weapons","TEST ONLY weapons") is not null,"failure retains last good: "+fail);
        }
        using var cancel=new CancellationTokenSource();cancel.Cancel();Check((await c.RefreshAsync(cancel.Token)).HasVerifiedCache,"caller cancellation retains cache");
        Check(c.FindVerified("images","TEST ONLY") is null,"no image-loading/context API");
    }
    h=new Fake(fixture){Mode="dns"};using(var c=new ReferenceCatalogClient(Options(ReferenceMode.ReadOnly,true,temp),h))Check((await c.RefreshAsync()).HasVerifiedCache && c.FindVerified("weapons","TEST ONLY weapons") is not null,"offline restart restores signed cache");
    h=new Fake(fixture);using(var c=new ReferenceCatalogClient(Options(ReferenceMode.Disabled,true,temp),h))Check((await c.RefreshAsync()).State=="disabled" && h.Calls==0 && c.FindVerified("weapons","TEST ONLY weapons") is null,"disable after cache prevents exposure");
    h=new Fake(fixture){Mode="dns"};using(var c=new ReferenceCatalogClient(Options(cache:temp) with{MaxCacheAge=TimeSpan.Zero},h))Check(!(await c.RefreshAsync()).HasVerifiedCache,"expired cache rejected");
    File.WriteAllText(Path.Combine(temp,"hunt-reference-v1.cache.json"),"broken");
    h=new Fake(fixture){Mode="500"};using(var c=new ReferenceCatalogClient(Options(cache:temp),h))Check(!(await c.RefreshAsync()).HasVerifiedCache,"corrupt disk cache ignored");
    h=new Fake(fixture);using(var c=new ReferenceCatalogClient(Options(),h,_=>throw new Exception("observer fails")))Check((await c.RefreshAsync()).HasVerifiedCache,"observer exception isolated");
    h=new Fake(fixture);using(var c=new ReferenceCatalogClient(Options() with{ManifestUrl=new("http://example.invalid/reference/catalog/v1/active.json")},h))Check((await c.RefreshAsync()).State=="unconfigured" && h.Calls==0,"insecure URL rejected without network");
    string blocked=Path.Combine(temp,"not-directory");File.WriteAllText(blocked,"file");
    h=new Fake(fixture);using(var c=new ReferenceCatalogClient(Options(cache:blocked),h))Check(!(await c.RefreshAsync()).HasVerifiedCache,"cache disk failure cannot commit partial snapshot");
    Console.WriteLine($"{passed} integration assertions passed (synthetic fixtures; no production push/archive execution).");
}
finally{Directory.Delete(temp,true);}

sealed class Fake(string root):HttpMessageHandler
{
    public int Calls;public string Mode="valid";
    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request,CancellationToken token)
    {
        Calls++;
        if(Mode=="dns")throw new HttpRequestException("Simulated DNS failure");
        if(Mode=="500")return new(HttpStatusCode.InternalServerError){RequestMessage=request};
        if(Mode=="timeout"){await Task.Delay(TimeSpan.FromSeconds(5),token);}
        if(Mode=="redirect")return new(HttpStatusCode.Redirect){RequestMessage=request};
        bool manifest=request.RequestUri!.AbsolutePath.EndsWith("active.json",StringComparison.Ordinal);
        var variant=Mode is "missing" or "unverified" or "draft" or "wrongrelation" ? Mode : "valid";
        string file=manifest?(Mode=="path"?"path.manifest.json":variant+".manifest.json"):variant+".json";
        byte[] data=File.ReadAllBytes(Path.Combine(root,file));
        if(Mode=="empty")data=[];
        if(Mode=="signature" && manifest)data=Encoding.UTF8.GetBytes("{\"algorithm\":\"ECDSA-P256-SHA256-DER\",\"payload\":\"e30=\",\"signature\":\"AA==\"}");
        if(Mode=="hash" && !manifest)data=Encoding.UTF8.GetBytes("{}");
        return new(HttpStatusCode.OK){RequestMessage=request,Content=new ByteArrayContent(data)};
    }
}
