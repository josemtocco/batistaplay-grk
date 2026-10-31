# BatistaPlay M3U – Playlist otimizada para SS IPTV

Playlist M3U gerada automaticamente a partir dos canais públicos de [batistaplay.net](https://www.batistaplay.net).

## Características

- **Atualização automática** a cada 6 horas via GitHub Actions
- **Teste real de streams** antes de incluir (verifica se o `.m3u8` responde e contém `#EXTM3U`)
- **Margem de graça**: um canal só é removido após **6 falhas consecutivas** (≈ 36 horas). Se voltar a funcionar, é recuperado imediatamente
- **Agrupado por categoria** (`group-title`): TV Aberta, Notícias, Filmes, Infantis, Religiosos, Variedades, Recomendados, Internacional
- **Logos** e metadados (`tvg-logo`, `tvg-name`, `tvg-id`) para melhor visualização no SS IPTV
- **Botões médios**: no SS IPTV vá em **Configurações → Aparência / Tamanho dos botões → Médio** (tanto para categorias quanto para canais)

## Como usar no SS IPTV

1. Abra o SS IPTV
2. Vá em **Lista de canais / Adicionar lista**
3. Cole a URL raw do arquivo:
   ```
   https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPOSITORIO/main/playlist.m3u
   ```
   (substitua pelos seus dados após publicar o repositório)
4. Em **Configurações do app**, defina o tamanho dos botões como **Médio**

## Como implantar no GitHub

1. Crie um repositório **público** no GitHub (ex: `batistaplay-m3u`)
2. Faça upload de todos os arquivos desta pasta (ou faça `git clone` / push)
3. Ative o GitHub Actions no repositório (aba Actions → Enable)
4. Rode o workflow manualmente a primeira vez (**Actions → Update Playlist → Run workflow**)
5. Após a primeira execução, a `playlist.m3u` estará disponível e será atualizada a cada 6 horas

### URL final da playlist

```
https://raw.githubusercontent.com/<seu-usuario>/<seu-repo>/main/playlist.m3u
```

Você também pode usar GitHub Pages se preferir um domínio customizado.

## Arquivos importantes

| Arquivo | Descrição |
|---------|-----------|
| `playlist.m3u` | Lista final pronta para o SS IPTV |
| `channels_state.json` | Estado de saúde de cada canal (fail_count) |
| `stats.json` | Estatísticas da última atualização |
| `scripts/update_playlist.py` | Script de coleta + teste + geração |
| `.github/workflows/update.yml` | Cron de 6 em 6 horas |

## Observações

- Os streams são de terceiros (batistaplay.net / logicahost etc.). A disponibilidade pode variar.
- O script não remove canais que param de funcionar momentaneamente – só após 6 atualizações seguidas de falha.
- Fonte oficial dos dados: API pública do batistaplay.net (Supabase).

## Licença

Uso livre. Os canais pertencem aos respectivos provedores.
