<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xmlns="http://www.opengis.net/sld"
  xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>gas_valves_status</Name>
    <UserStyle>
      <Title>Gaz Vanaları - Ortak Durum Standardı</Title>
      <Abstract>Vanaları borulardan ayıran, kenarlıklı ve durum renkli nokta sembolü.</Abstract>
      <FeatureTypeStyle>
        <Rule>
          <Name>aktif</Name><Title>Aktif vana</Title>
          <ogc:Filter><ogc:Or>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>aktif</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>active</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>open</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>açık</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>acik</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:Or></ogc:Filter>
          <PointSymbolizer><Graphic><Mark><WellKnownName>circle</WellKnownName>
            <Fill><CssParameter name="fill">#16a34a</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#ffffff</CssParameter><CssParameter name="stroke-width">2</CssParameter></Stroke>
          </Mark><Size>12</Size></Graphic></PointSymbolizer>
        </Rule>
        <Rule>
          <Name>pasif</Name><Title>Pasif vana</Title>
          <ogc:Filter><ogc:Or>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>pasif</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>inactive</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>closed</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>kapalı</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>kapali</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:Or></ogc:Filter>
          <PointSymbolizer><Graphic><Mark><WellKnownName>circle</WellKnownName>
            <Fill><CssParameter name="fill">#dc2626</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#ffffff</CssParameter><CssParameter name="stroke-width">2</CssParameter></Stroke>
          </Mark><Size>12</Size></Graphic></PointSymbolizer>
        </Rule>
        <Rule>
          <Name>bakimda</Name><Title>Bakımda vana</Title>
          <ogc:Filter><ogc:Or>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>bakımda</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>bakimda</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>maintenance</ogc:Literal></ogc:PropertyIsEqualTo>
            <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>tamirde</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:Or></ogc:Filter>
          <PointSymbolizer><Graphic><Mark><WellKnownName>circle</WellKnownName>
            <Fill><CssParameter name="fill">#f97316</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#ffffff</CssParameter><CssParameter name="stroke-width">2</CssParameter></Stroke>
          </Mark><Size>12</Size></Graphic></PointSymbolizer>
        </Rule>
        <Rule>
          <Name>bilinmeyen</Name><Title>Bilinmeyen durum</Title><ElseFilter/>
          <PointSymbolizer><Graphic><Mark><WellKnownName>circle</WellKnownName>
            <Fill><CssParameter name="fill">#6b7280</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#ffffff</CssParameter><CssParameter name="stroke-width">2</CssParameter></Stroke>
          </Mark><Size>12</Size></Graphic></PointSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
