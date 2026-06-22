import 'dart:io';

import 'package:flutter/material.dart';
import 'package:gal/gal.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

/// Baixa o vídeo em [url] e salva no rolo da câmera (álbum "DarkFlow").
///
/// Mostra snackbars de progresso/erro via o [ScaffoldMessenger] do [context].
/// Captura o messenger antes do primeiro await para não usar o context depois.
Future<void> saveVideoToGallery(BuildContext context, String url) async {
  final messenger = ScaffoldMessenger.of(context);
  messenger.showSnackBar(
    const SnackBar(content: Text('Baixando vídeo...')),
  );
  File? temp;
  try {
    final response = await http.get(Uri.parse(url));
    if (response.statusCode != 200) {
      throw Exception('HTTP ${response.statusCode}');
    }
    final dir = await getTemporaryDirectory();
    final stamp = DateTime.now().millisecondsSinceEpoch;
    temp = File('${dir.path}/darkflow_$stamp.mp4');
    await temp.writeAsBytes(response.bodyBytes);

    await Gal.putVideo(temp.path, album: 'DarkFlow');

    messenger.showSnackBar(
      const SnackBar(content: Text('Vídeo salvo na galeria.')),
    );
  } on GalException catch (e) {
    messenger.showSnackBar(
      SnackBar(content: Text('Não foi possível salvar: ${e.type.message}')),
    );
  } catch (_) {
    messenger.showSnackBar(
      const SnackBar(content: Text('Não foi possível baixar o vídeo.')),
    );
  } finally {
    // Limpa o arquivo temporário; a cópia na galeria permanece.
    if (temp != null && await temp.exists()) {
      await temp.delete();
    }
  }
}
