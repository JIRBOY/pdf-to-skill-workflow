---
name: TC1000-TwinCAT3-ADS-NET-Programming
description: 使用 TwinCAT 3 ADS .NET V7 API 编写 C# 代码与 TwinCAT PLC/NC 设备通信。涵盖 AdsClient 连接管理、符号访问、通知、批量 Sum 命令、Reactive Extensions、ADS Server 实现等。
type: programming
---

# TwinCAT 3 ADS .NET V7 编程技能

基于 TC1000 手册 (版本 1.4.0, 2026-03-26) — TwinCAT.Ads.dll V7.x API 完整指南。

## 何时触发

- 编写 C# 代码通过 ADS 与 TwinCAT PLC/NC/CNC 通信
- 使用 `TwinCAT.Ads`、`TwinCAT.Ads.SumCommand`、`TwinCAT.Ads.Reactive`、`TwinCAT.Ads.Server` 命名空间
- 需要 Read/Write/ReadWrite/Notification/SumCommand/Server 等 API 参考
- 从旧版 V4/V5/V6 API 迁移到 V7
- 实现自定义 ADS Server 或使用 Reactive Extensions

> **重要**: V7 API 与 V4/V5/V6 不兼容。旧版使用 `TcAdsClient`，新版使用 `AdsClient` / `AdsConnection`。方法签名、返回类型、命名空间均有变化。

---

## 1. 快速开始

### 1.1 安装

```bash
dotnet add package TwinCAT.Ads
```

### 1.2 命名空间

| 命名空间 | 用途 |
|----------|------|
| `TwinCAT.Ads` | 核心 API — AdsClient, AdsConnection, 通知, 状态控制 |
| `TwinCAT.Ads.SumCommand` | 批量操作 — 一次请求读写多个变量 |
| `TwinCAT.Ads.Reactive` | Reactive Extensions — IObservable 模式 |
| `TwinCAT.Ads.Server` | ADS Server — 实现自定义 ADS 服务端 |
| `TwinCAT.Ads.TcpRouter` | TCP/IP 路由 — 路由配置管理 |
| `TwinCAT` | 通用类型 — Session, 异常, 连接状态 |

### 1.3 最简示例

```csharp
using TwinCAT.Ads;

using (AdsClient client = new AdsClient())
{
    client.Connect(AmsNetId.Local, 851);  // 851 = TC3 PLC 运行时系统 1

    // 符号访问（推荐）
    ResultWrite wr = client.WriteValue("MAIN.nCounter", 42);
    ResultValue<uint> rr = client.ReadValue<uint>("MAIN.nCounter");
    if (rr.Succeeded)
        Console.WriteLine(rr.Value);
}
```

---

## 2. 数据访问方式

V7 API 提供 **4 种** 数据访问方式，按推荐程度排序：

### 2.1 符号路径访问 (推荐)

通过变量名直接读写，无需预先获取句柄。

```csharp
// 同步
ResultWrite wr = client.WriteValue("MAIN.nCounter", 42);
ResultValue<uint> rr = client.ReadValue<uint>("MAIN.nCounter");

// 异步
ResultWrite wr = await client.WriteValueAsync("MAIN.nCounter", 42, cancel);
ResultValue<uint> rr = await client.ReadValueAsync<uint>("MAIN.nCounter", cancel);
```

### 2.2 符号句柄访问 (高性能场景)

先创建句柄，后续操作用句柄代替字符串路径。

```csharp
uint handle = 0;
ResultHandle rh = await client.CreateVariableHandleAsync("MAIN.nCounter", cancel);
if (rh.Succeeded)
{
    handle = rh.Handle;
    try
    {
        await client.WriteAnyAsync(handle, 42, cancel);
        ResultValue<uint> rr = await client.ReadAnyAsync<uint>(handle, cancel);
    }
    finally
    {
        await client.DeleteVariableHandleAsync(handle, cancel);  // 必须释放!
    }
}
```

### 2.3 IndexGroup/IndexOffset 访问

通过数字索引直接访问内存地址。

```csharp
// 读取 %M 字段字节偏移 0
ResultValue<byte[]> rr = await client.ReadAnyAsync<byte[]>(0x4020, 0x0, 10, cancel);

// 写入 %M 字段字节偏移 0
byte[] data = new byte[] { 0x01, 0x02, 0x03 };
await client.WriteAnyAsync(0x4020, 0x0, data, cancel);
```

### 2.4 ANYTYPE 结构化访问

通过 Struct 定义直接映射 PLC 结构体。

```csharp
[StructLayout(LayoutKind.Sequential, Pack = 8)]
struct PlcData
{
    public bool bEnable;       // BOOL
    public byte byReserved;    // 填充
    public ushort usValue;     // UINT
    public uint uiCounter;     // UDINT
    public double dSetpoint;   // LREAL
}

// 读取
ResultValue<PlcData> rr = await client.ReadAnyAsync<PlcData>(0x4020, 0x0, cancel);

// 写入
PlcData data = new PlcData { bEnable = true, usValue = 100, dSetpoint = 3.14 };
await client.WriteAnyAsync(0x4020, 0x0, data, cancel);
```

> **结构体要求**: 使用 `Pack = 8`（默认 PLC 对齐），字符串用 `MarshalAs(UnmanagedType.ByValTStr, SizeConst = N)`。

---

## 3. AdsClient 完整 API

### 3.1 连接管理

```csharp
// 创建并连接
AdsClient client = new AdsClient();
client.Connect(AmsNetId.Local, 851);
client.Connect("192.168.1.10.1.1", 851);           // 字符串 NetId
client.Connect(new AmsNetId("192.168.1.10.1.1"), 851); // AmsNetId 对象

// 连接状态
bool connected = client.IsConnected;
ConnectionState state = client.ConnectionState;     // Disconnected/Connecting/Connected/Disconnecting

// 断开
client.Disconnect();

// 推荐: using 语句自动释放
using (AdsClient client = new AdsClient())
{
    client.Connect(AmsNetId.Local, 851);
    // ...
}
```

### 3.2 读取操作

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `ReadValue<T>(string symbolPath)` | `ResultValue<T>` | 按符号路径读取 |
| `ReadValueAsync<T>(symbolPath, cancel)` | `Task<ResultValue<T>>` | 异步版 |
| `ReadAny<T>(indexGroup, indexOffset, cancel)` | `ResultValue<T>` | 按索引组读取 |
| `ReadAnyAsync<T>(indexGroup, indexOffset, cancel)` | `Task<ResultValue<T>>` | 异步版 |
| `ReadAny<T>(indexGroup, indexOffset, type, cancel)` | `ResultValue<T>` | 指定 Type 读取 |
| `ReadBytes(indexGroup, indexOffset, length, cancel)` | `ResultReadBytes` | 读取原始字节 |
| `ReadBytesAsync(...)` | `Task<ResultReadBytes>` | 异步版 |
| `ReadState()` | `ResultReadAdsState` | 读取 ADS + 设备状态 |
| `ReadStateAsync(cancel)` | `Task<ResultReadAdsState>` | 异步版 |
| `ReadDeviceInfo()` | `ResultDeviceInfo` | 读取设备信息 |
| `ReadDeviceInfoAsync(cancel)` | `Task<ResultDeviceInfo>` | 异步版 |

### 3.3 写入操作

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `WriteValue(string symbolPath, object value)` | `ResultWrite` | 按符号路径写入 |
| `WriteValueAsync(symbolPath, value, cancel)` | `Task<ResultWrite>` | 异步版 |
| `WriteAny(indexGroup, indexOffset, value, cancel)` | `ResultWrite` | 按索引组写入 |
| `WriteAnyAsync(indexGroup, indexOffset, value, cancel)` | `Task<ResultWrite>` | 异步版 |
| `WriteBytes(indexGroup, indexOffset, data, cancel)` | `ResultWrite` | 写入原始字节 |
| `WriteControl(adsState, deviceState, data, cancel)` | `ResultWriteControl` | 写入控制状态 |
| `WriteControlAsync(...)` | `Task<ResultWriteControl>` | 异步版 |

### 3.4 读写操作 (ReadWrite)

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `ReadWrite<TWrite, TRead>(ig, io, writeValue, cancel)` | `ResultReadWrite<TRead>` | 同时读写 |
| `ReadWriteAsync<TWrite, TRead>(ig, io, writeValue, cancel)` | `Task<ResultReadWrite<TRead>>` | 异步版 |
| `ReadWriteBytes(ig, io, writeData, readLength, cancel)` | `ResultReadWriteBytes` | 原始字节版 |

### 3.5 句柄管理

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `CreateVariableHandle(symbolPath, cancel)` | `ResultHandle` | 创建变量句柄 |
| `CreateVariableHandleAsync(...)` | `Task<ResultHandle>` | 异步版 |
| `DeleteVariableHandle(handle, cancel)` | `ResultAds` | 删除变量句柄 |
| `DeleteVariableHandleAsync(...)` | `Task<ResultAds>` | 异步版 |

### 3.6 通知

```csharp
// 注册通知
ResultHandle rh = await client.AddDeviceNotificationAsync(
    "MAIN.nCounter",              // 符号路径
    sizeof(uint),                 // 数据大小
    new NotificationSettings(AdsTransMode.OnChange, 200, 0),  // 设置
    null,                         // 用户数据
    cancel);

if (rh.Succeeded)
{
    uint notifHandle = rh.Handle;
    // ... 等待通知 ...
    await client.DeleteDeviceNotificationAsync(notifHandle, cancel);  // 必须释放!
}

// 事件处理
client.AdsNotification += (sender, e) =>
{
    uint value = BinaryPrimitives.ReadUInt32LittleEndian(e.Data.Span);
    // 注意: 此事件在非 UI 线程触发
};
```

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `AddDeviceNotification(symbolPath, length, settings, userData, cancel)` | `ResultHandle` | 添加通知 |
| `AddDeviceNotificationAsync(...)` | `Task<ResultHandle>` | 异步版 |
| `DeleteDeviceNotification(handle, cancel)` | `ResultAds` | 删除通知 |
| `DeleteDeviceNotificationAsync(...)` | `Task<ResultAds>` | 异步版 |

### 3.7 状态控制

```csharp
// 读取状态
ResultReadAdsState rs = await client.ReadStateAsync(cancel);
AdsState adsState = rs.AdsState;       // Idle/Run/Stop/Config/Error...
ushort deviceState = rs.DeviceState;

// 写控制 — 启动 PLC
await client.WriteControlAsync(AdsStateCommand.Start, 0, null, cancel);

// 写控制 — 停止 PLC
await client.WriteControlAsync(AdsStateCommand.Stop, 0, null, cancel);
```

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `WriteControl(command, deviceState, data, cancel)` | `ResultWriteControl` | 通过命令写入 |
| `WriteControlAsync(...)` | `Task<ResultWriteControl>` | 异步版 |
| `WriteControl(adsState, deviceState, data, cancel)` | `ResultWriteControl` | 通过状态值写入 |

### 3.8 RPC 调用

```csharp
// 调用 PLC 中的方法（如 TcReflection 功能块方法）
ResultRpcMethod result = await client.InvokeRpcMethodAsync(
    "MAIN.MyInstance",    // 实例路径
    "MyMethod",            // 方法名
    new object[] { arg1, arg2 },  // 参数
    cancel);
```

| 方法 | 返回类型 | 说明 |
|------|----------|------|
| `InvokeRpcMethod(instancePath, methodName, parameters, cancel)` | `ResultRpcMethod` | RPC 方法调用 |
| `InvokeRpcMethodAsync(...)` | `Task<ResultRpcMethod>` | 异步版 |

### 3.9 Raw 访问 (ITcAdsRaw / ITcAdsRawAny)

用于需要完全控制字节流的底层场景：

```csharp
ITcAdsRaw raw = client;  // AdsClient 实现 ITcAdsRaw
raw.Write(indexGroup, indexOffset, data, offset, length, cancel);
raw.Read(indexGroup, indexOffset, buffer, offset, length, cancel);
```

---

## 4. 通知模式详解

### 4.1 NotificationSettings

```csharp
new NotificationSettings(
    AdsTransMode.OnChange,   // 传输模式
    200,                      // cycleTime (ms) — 检查间隔
    0                         // maxDelay (ms) — 0 表示无延迟
)
```

| AdsTransMode | 行为 |
|--------------|------|
| `None` | 未初始化 |
| `Cyclic` | 按 cycleTime 周期触发 |
| `OnChange` | 值变化时触发（在 cycleTime 内检测） |
| `SynchEndOfCycle` *(V7 新增)* | PLC 周期结束时触发 |
| `SynchEndOfTask` *(V7 新增)* | 任务周期结束时触发 |

### 4.2 基于 Symbol 的通知

```csharp
ISymbolLoader loader = SymbolLoaderFactory.Create(client, SymbolLoaderSettings.Default);
Symbol symbol = (Symbol)loader.Symbols["MAIN.nCounter"];

symbol.NotificationSettings = new NotificationSettings(AdsTransMode.OnChange, 500, 0);
symbol.ValueChanged += (sender, e) =>
{
    int value = (int)e.Value;  // 自动类型转换
};

// 注册通知（通过 ValueChanged += 触发）
// 取消注册（通过 ValueChanged -= 移除）
```

---

## 5. SumCommand 批量操作

一次 ADS 请求执行最多 500 个子命令。

### 5.1 基本用法

```csharp
using TwinCAT.Ads.SumCommand;

// 批量读取
var sumRead = new SumSymbolRead(client, SumCommandMode.UseSumCommand);
sumRead.Add("MAIN.var1", typeof(int));
sumRead.Add("MAIN.var2", typeof(double));
sumRead.Add("MAIN.var3", typeof(string));

ResultSumValues result = await sumRead.ReadAsync(cancel);

if (result.AllSucceeded())
{
    int v1 = result.GetValue<int>(0);
    double v2 = result.GetValue<double>(1);
    string v3 = result.GetValue<string>(2);
}
```

### 5.2 批量写入

```csharp
var sumWrite = new SumSymbolWrite(client, SumCommandMode.UseSumCommand);
sumWrite.Add("MAIN.var1", 42);
sumWrite.Add("MAIN.var2", 3.14);
sumWrite.Add("MAIN.var3", "hello");

await sumWrite.WriteAsync(cancel);
```

### 5.3 句柄批量操作

```csharp
// 批量创建句柄
var createHandles = new SumCreateHandles(client);
createHandles.Add("MAIN.var1");
createHandles.Add("MAIN.var2");
createHandles.Add("MAIN.var3");
ResultSumHandles hResult = await createHandles.ExecuteAsync(cancel);

// 批量读取
var handleRead = new SumHandleRead(client);
handleRead.Add(hResult.GetHandle(0), typeof(int));
handleRead.Add(hResult.GetHandle(1), typeof(double));
ResultSumReadRaw rResult = await handleRead.ReadAsync(cancel);

// 批量释放句柄
var release = new SumReleaseHandles(client);
release.Add(hResult.GetHandle(0));
release.Add(hResult.GetHandle(1));
release.Add(hResult.GetHandle(2));
await release.ExecuteAsync(cancel);
```

### 5.4 错误策略

```csharp
sumRead.ErrorStrategy = SumCommandErrorStrategy.ContinueOnError;  // 遇到错误继续
sumRead.FallbackMode = SumFallbackMode.Automatic;                 // Sum 失败自动降级为单独请求
```

| SumCommandErrorStrategy | 行为 |
|------------------------|------|
| `ContinueOnError` | 单个子命令失败时继续执行其余 |
| `AbortOnError` | 遇到第一个错误时中止 |

| SumFallbackMode | 行为 |
|-----------------|------|
| `Automatic` | Sum 命令失败时自动降级为离散请求 |
| `Disabled` | 不使用降级 |

### 5.5 SumCommand 结果检查

```csharp
bool ok = result.AllSucceeded();       // 全部成功
bool anyFail = result.OneFailed();     // 至少一个失败
bool allFail = result.AllFailed();     // 全部失败
int successCount = result.SucceededCount;
int failedCount = result.FailedCount;
AdsErrorCode firstError = result.FirstSubError();
AdsErrorCode overall = result.OverallError();
bool isFallback = result.IsFallback;   // 是否使用了降级
```

---

## 6. Reactive Extensions

```csharp
using TwinCAT.Ads.Reactive;
using System.Reactive;
using System.Reactive.Linq;
```

### 6.1 值变化 Observable

```csharp
IObservable<ValueNotificationEventArgs<uint>> obs =
    client.WhenValueChanged<uint>("MAIN.nCounter", new NotificationSettings(AdsTransMode.OnChange, 100, 0));

obs.Subscribe(e => Console.WriteLine($"Value: {e.Value}"));
```

### 6.2 Symbol Observable

```csharp
ISymbolLoader loader = SymbolLoaderFactory.Create(client, SymbolLoaderSettings.Default);
IValueSymbol<int> symbol = (IValueSymbol<int>)loader.Symbols["MAIN.nCounter"];

symbol.WhenValueChanged()
    .Subscribe(v => Console.WriteLine($"Changed: {v}"));
```

### 6.3 轮询

```csharp
// 通过 SumCommand 轮询多个变量
IObservable<ResultSumValues2<int>> obs =
    SumSymbolRead.PollValues<int>(client, TimeSpan.FromMilliseconds(100), cancel,
        "MAIN.var1", "MAIN.var2", "MAIN.var3");

obs.Subscribe(result =>
{
    // 处理轮询结果
});
```

### 6.4 写入 Observable

```csharp
IObservable<int> writeStream = ...;  // 你的值流
symbol.WriteValues(writeStream);     // 订阅写入
```

---

## 7. ADS Server 实现

### 7.1 基本 Server

```csharp
using TwinCAT.Ads.Server;

class MyAdsServer : AdsServer
{
    public MyAdsServer(AmsNetId netId, ushort port) : base(netId, port) { }

    protected override async Task OnReadAsync(OnReadEventArgs args)
    {
        // 处理 Read 请求
        args.Data = new byte[] { 0x01, 0x02 };
        args.Result = AdsErrorCode.NoError;
    }

    protected override async Task OnWriteAsync(OnWriteEventArgs args)
    {
        // 处理 Write 请求
        args.Result = AdsErrorCode.NoError;
    }
}

// 使用
var server = new MyAdsServer(AmsNetId.Local, 26000);
await server.ConnectServerAsync();
```

### 7.2 SymbolicServer

```csharp
class MySymbolicServer : AdsSymbolicServer
{
    protected override Task OnCreateSymbols()
    {
        // 创建符号树
        return Task.CompletedTask;
    }
}
```

### 7.3 Server 关键方法

| 方法 | 说明 |
|------|------|
| `ConnectServer()` / `ConnectServerAsync()` | 连接 ADS 路由器 |
| `Disconnect()` | 断开连接 |
| `OnReadAsync(args)` | 处理 Read 请求 |
| `OnWriteAsync(args)` | 处理 Write 请求 |
| `OnReadWriteAsync(args)` | 处理 ReadWrite 请求 |
| `OnReadDeviceStateAsync(args)` | 处理 ReadState 请求 |
| `OnWriteControlAsync(args)` | 处理 WriteControl 请求 |
| `FireNotificationAsync(address, data)` | 主动推送通知 |
| `FireNotificationsAsync()` | 推送所有待发送的通知 |

---

## 8. Result 类型模式

所有操作返回统一的结果模式：

```csharp
// 通用模式
ResultValue<T> result = await client.ReadValueAsync<T>("MAIN.var", cancel);
if (result.Succeeded)
{
    T value = result.Value;
}
else
{
    AdsErrorCode error = result.ErrorCode;
    // 处理错误
}

// 简写
result.ThrowOnError();  // 失败时抛出 AdsErrorException
```

### 常用 Result 类型

| 类型 | 用途 |
|------|------|
| `ResultValue<T>` | 泛型值操作结果 |
| `ResultWrite` | 写入操作结果 |
| `ResultReadBytes` | 字节读取结果 (`Data` 属性为 `byte[]`) |
| `ResultReadWrite<T>` | 读写操作结果 |
| `ResultHandle` | 句柄操作结果 (`Handle` 属性) |
| `ResultDeviceInfo` | 设备信息结果 (`Name`, `Version`) |
| `ResultReadAdsState` | 状态读取结果 (`AdsState`, `DeviceState`) |
| `ResultWriteControl` | 控制写入结果 |
| `ResultRpcMethod` | RPC 调用结果 (`ReturnValue`) |
| `ResultSumValues` | SumCommand 结果 |
| `ResultAds` | 通用 ADS 结果 |

### 异常类型

| 异常 | 触发场景 |
|------|----------|
| `AdsException` | ADS 操作基础异常 |
| `AdsErrorException` | 包含具体 AdsErrorCode 的异常 |
| `AdsSumCommandException` | SumCommand 失败 |
| `SumCommandNotAllowedException` | Sum 命令不被支持 |
| `ClientNotConnectedException` | 客户端未连接 |
| `SessionNotConnectedException` | Session 未连接 |
| `ServerNotConnectedException` | Server 未连接 |
| `RouterException` | 路由器操作异常 |

---

## 9. 关键枚举值

### AdsState

| 值 | 说明 |
|----|------|
| `Invalid` | 无效/未初始化 |
| `Idle` | 空闲 |
| `Reset` | 重置 |
| `Init` | 初始化 |
| `Start` | 启动 |
| `Run` | 运行 |
| `Stop` | 停止 |
| `SaveConfig` | 保存配置 |
| `LoadConfig` | 加载配置 |
| `PowerFailure` | 断电 |
| `PowerGood` | 电源恢复 |
| `Error` | 错误 |
| `Shutdown` | 关机 |

### AdsStateCommand (WriteControl 用)

| 值 | 说明 |
|----|------|
| `Start` | 启动设备 |
| `Stop` | 停止设备 |
| `Reset` | 重置设备 |

### AdsTransMode (通知传输模式)

| 值 | 说明 |
|----|------|
| `None` | 未初始化 |
| `Cyclic` | 周期触发 |
| `OnChange` | 变化触发 |
| `SynchEndOfCycle` | PLC 周期结束触发 |
| `SynchEndOfTask` | 任务周期结束触发 |

### AdsDataTypeId

| 值 | 名称 | 类型 |
|----|------|------|
| 2 | `ADST_INT16` | INT |
| 3 | `ADST_INT32` | DINT |
| 4 | `ADST_REAL32` | REAL |
| 5 | `ADST_REAL64` | LREAL |
| 16 | `ADST_INT8` | SINT |
| 17 | `ADST_UINT8` | USINT/BYTE |
| 18 | `ADST_UINT16` | UINT/WORD |
| 19 | `ADST_UINT32` | UDINT/DWORD |
| 20 | `ADST_INT64` | LINT |
| 21 | `ADST_UINT64` | ULINT/LWORD |
| 30 | `ADST_STRING` | STRING |
| 31 | `ADST_WSTRING` | WSTRING |
| 12 | `ADST_VARIANT` | ANY |

### AmsPort (常用)

| 端口 | 说明 |
|------|------|
| `1` | ADS Router |
| `30` | Authorization |
| `100` | Logger |
| `801` | TC2 PLC Runtime 1 |
| `851` | TC3 PLC Runtime 1 |
| `852` | TC3 PLC Runtime 2 |
| `500` | NC Axis |
| `501` | NC SAF |
| `11000` | NC Control |
| `10000` | System Service |

---

## 10. 编程最佳实践

### 10.1 优先使用符号访问

```csharp
// 推荐: 符号路径
client.ReadValue<uint>("MAIN.nCounter");

// 次选: 符号句柄 (高频访问时)
uint h = (await client.CreateVariableHandleAsync("MAIN.nCounter")).Handle;
client.ReadAny<uint>(h);
await client.DeleteVariableHandleAsync(h);

// 避免: 直接使用索引组 (除非访问底层内存)
client.ReadAny<uint>(0x4020, 0x0);
```

### 10.2 异步编程

```csharp
// 始终使用 async/await 模式
public async Task<uint> ReadCounterAsync(CancellationToken cancel = default)
{
    using var client = new AdsClient();
    await client.ConnectAsync(AmsNetId.Local, 851, cancel);
    var result = await client.ReadValueAsync<uint>("MAIN.nCounter", cancel);
    result.ThrowOnError();
    return result.Value;
}
```

### 10.3 批量操作减少网络开销

```csharp
// 读取 10 个变量 — 使用 SumCommand
var sum = new SumSymbolRead(client);
sum.Add("MAIN.var1", typeof(int));
sum.Add("MAIN.var2", typeof(double));
// ... 最多 500 个
ResultSumValues r = await sum.ReadAsync(cancel);

// 比 10 次单独 ReadValueAsync 高效得多
```

### 10.4 通知 vs 轮询

```csharp
// 需要实时更新 → 使用通知 (低开销)
client.AdsNotification += Handler;
await client.AddDeviceNotificationAsync("MAIN.var", 4,
    new NotificationSettings(AdsTransMode.OnChange, 100, 0), null, cancel);

// 需要采样数据 → 使用轮询或 Reactive Polling
var obs = SumSymbolRead.PollValues<int>(client, TimeSpan.FromMilliseconds(100), cancel,
    "MAIN.var1", "MAIN.var2");
```

### 10.5 资源释放

```csharp
// 句柄必须释放
uint handle = 0;
try
{
    handle = (await client.CreateVariableHandleAsync(name)).Handle;
    // 使用...
}
finally
{
    if (handle != 0)
        await client.DeleteVariableHandleAsync(handle, cancel);
}

// 通知必须注销
uint notifHandle = 0;
try
{
    notifHandle = (await client.AddDeviceNotificationAsync(...)).Handle;
    // 使用...
}
finally
{
    if (notifHandle != 0)
        await client.DeleteDeviceNotificationAsync(notifHandle, cancel);
}

// 优先使用 using 语句
using (AdsClient client = new AdsClient()) { ... }
```

### 10.6 错误处理

```csharp
// 检查结果码
var result = await client.ReadValueAsync<int>("MAIN.var", cancel);
if (!result.Succeeded)
{
    // 检查具体错误
    if (result.ErrorCode == AdsErrorCode.DeviceSymbolNotFound)
        // 变量不存在
    else if (result.ErrorCode == AdsErrorCode.DeviceNotReady)
        // PLC 未运行
}

// 或抛出异常
result.ThrowOnError();  // 失败时抛出 AdsErrorException
```

### 10.7 UI 线程同步

```csharp
// AdsNotification 事件在非 UI 线程触发
private SynchronizationContext _uiContext;

public void Init()
{
    _uiContext = SynchronizationContext.Current;
    client.AdsNotification += (sender, e) =>
    {
        _uiContext.Post(_ => UpdateUI(e), null);
    };
}
```

---

## 11. 类型映射 (PLC → .NET)

| PLC 类型 | .NET 类型 | AdsDataTypeId |
|----------|-----------|---------------|
| BOOL | `bool` | — |
| SINT / BYTE | `sbyte` / `byte` | `ADST_INT8` / `ADST_UINT8` |
| INT / WORD | `short` / `ushort` | `ADST_INT16` / `ADST_UINT16` |
| DINT / DWORD | `int` / `uint` | `ADST_INT32` / `ADST_UINT32` |
| LINT / LWORD | `long` / `ulong` | `ADST_INT64` / `ADST_UINT64` |
| REAL | `float` | `ADST_REAL32` |
| LREAL | `double` | `ADST_REAL64` |
| STRING[n] | `string` | `ADST_STRING` |
| WSTRING[n] | `string` | `ADST_WSTRING` |
| TIME | `TimeSpan` | — |
| DATE | `DateTime` | — |
| TOD | `TimeSpan` | — |
| DT | `DateTime` | — |

> **STRING 注意事项**: PLC STRING[n] 在 .NET 中映射为 n+1 字节（含终止符）。使用 `ReadValue<string>()` 时自动处理。
