"""Descriptors for Emby-managed external subtitles. Never burns video."""
def subtitle_options(streams):
    result=[]
    for stream in streams:
        if stream.get('Type')!='Subtitle' or not stream.get('IsExternal'):continue
        index=stream.get('Index');codec=(stream.get('Codec') or '').lower()
        if not isinstance(index,int) or index<0:continue
        supported=codec in ('srt','subrip','ass','ssa','vtt','webvtt','mov_text','text') or stream.get('IsTextSubtitleStream') is True
        fmt='ass' if codec in ('ass','ssa') else 'vtt' if codec in ('vtt','webvtt') else 'srt'
        title=stream.get('DisplayTitle') or stream.get('Title') or ' · '.join(x for x in (stream.get('Language'),codec.upper()) if x) or f'字幕 {index}'
        result.append({'index':index,'title':title,'format':fmt,'supported':supported,'default':bool(stream.get('IsDefault')),'forced':bool(stream.get('IsForced'))})
    return result

def merge_subtitle_streams(playback_streams,detail,source_id):
    """Combine selected-source and item-level tracks without mixing editions."""
    streams=list(playback_streams or [])
    for source in detail.get('MediaSources') or []:
        if str(source.get('Id'))==str(source_id):streams.extend(source.get('MediaStreams') or [])
    streams.extend(detail.get('MediaStreams') or [])
    merged={}
    for stream in streams:
        key=(stream.get('Type'),stream.get('Index'))
        merged[key]={**merged.get(key,{}),**stream}
    return list(merged.values())
