"""测试 IMDb HistogramValues 类型字段 + 完整数据"""
import requests
import json

HEADERS_GRAPHQL = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/graphql+json, application/json',
    'x-imdb-client-name': 'imdb-web-next-amsterdam',
    'x-imdb-user-country': 'US',
    'x-imdb-user-language': 'en-US',
    'Origin': 'https://www.imdb.com',
    'Referer': 'https://www.imdb.com/title/tt1517268/ratings/',
}
URL = 'https://api.graphql.imdb.com/'

def introspect_histogramvalues():
    q = '''query {
  __type(name: "HistogramValues") {
    name kind
    fields {
      name description
      type { name kind ofType { name kind } }
    }
  }
}'''
    resp = requests.post(URL, json={'query': q}, headers=HEADERS_GRAPHQL, timeout=10)
    data = resp.json()
    t = (data.get('data') or {}).get('__type')
    if t:
        print(f'Type HistogramValues (kind={t.get("kind")}):')
        for f in (t.get('fields') or []):
            ti = f.get('type') or {}
            tn = ti.get('name') or (ti.get('ofType') or {}).get('name', '?')
            print(f'  {f["name"]}: {tn}')

def test_full_histogram():
    """尝试用所有可能的 HistogramValues 字段获取完整数据"""
    # 先通过内省获取 HistogramValues 的字段
    q_intro = '''query { __type(name: "HistogramValues") { fields { name type { name } } } }'''
    resp = requests.post(URL, json={'query': q_intro}, headers=HEADERS_GRAPHQL, timeout=10)
    data = resp.json()
    fields = (data.get('data') or {}).get('__type', {}).get('fields', []) or []
    field_names = [f['name'] for f in fields if f]
    print(f'HistogramValues fields: {field_names}')
    
    # 构建查询
    if field_names:
        fields_query = ' '.join(field_names)
        q = f'''query {{
  title(id: "tt1517268") {{
    aggregateRatingsBreakdown {{
      histogram {{
        histogramValues {{
          {fields_query}
        }}
      }}
    }}
  }}
}}'''
        resp2 = requests.post(URL, json={'query': q}, headers=HEADERS_GRAPHQL, timeout=10)
        print(f'\nFull histogram query status: {resp2.status_code}')
        print(f'Response: {json.dumps(resp2.json(), indent=2)[:3000]}')

if __name__ == '__main__':
    print('=== Introspect HistogramValues type ===')
    introspect_histogramvalues()
    
    print('\n=== Full histogram data ===')
    test_full_histogram()
