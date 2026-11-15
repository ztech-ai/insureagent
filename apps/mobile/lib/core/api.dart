import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiFailure implements Exception {
  final int status;
  final String code;
  ApiFailure(this.status, this.code);
  @override
  String toString() => switch (status) {
    401 => '会话已过期，请重新登录；本机草稿仍保留。',
    409 => '资料已有更新，请刷新后再操作。',
    410 => '此记录已删除，不能重新上传。',
    413 => '录音超过大小限制。',
    _ => '操作未完成（$code），请稍后重试。',
  };
}

class AlphaApi {
  final Uri base;
  final http.Client client;
  String? token;
  AlphaApi(String address, {http.Client? client})
    : base = Uri.parse(address),
      client = client ?? http.Client() {
    if (base.host.isEmpty ||
        base.userInfo.isNotEmpty ||
        base.query.isNotEmpty ||
        base.fragment.isNotEmpty ||
        (base.path != '' && base.path != '/') ||
        (base.scheme != 'https' && !(kDebugMode && base.scheme == 'http'))) {
      throw ArgumentError('请输入服务根地址；正式构建只允许 HTTPS');
    }
  }

  Future<dynamic> request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Uint8List? audio,
    Map<String, String>? query,
  }) async {
    final uri = base.resolve(path).replace(queryParameters: query);
    final request = http.Request(method, uri);
    request.headers['Accept'] = 'application/json';
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    if (audio != null) {
      request.headers['Content-Type'] = 'audio/wav';
      request.bodyBytes = audio;
    } else if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    http.Response response;
    try {
      response = await (() async => http.Response.fromStream(
        await client.send(request),
      ))().timeout(const Duration(seconds: 60));
    } catch (_) {
      throw ApiFailure(0, 'network_unavailable');
    }
    final dynamic decoded = response.body.isEmpty
        ? null
        : jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode >= 400) {
      throw ApiFailure(
        response.statusCode,
        decoded is Map
            ? '${decoded['detail'] ?? 'request_failed'}'
            : 'request_failed',
      );
    }
    return decoded;
  }

  void close() => client.close();
}
