<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xmlns="http://www.opengis.net/sld"
  xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>gas_pipes_status</Name>
    <UserStyle>
      <Title>Gaz Boruları - Ortak Durum Standardı</Title>
      <Abstract>Renk durumu, çizgi kalınlığı boru türünü gösterir.</Abstract>
      <FeatureTypeStyle>
        <Rule>
          <Name>aktif_main_line</Name><Title>Aktif ana hat</Title>
          <ogc:Filter><ogc:And>
            <ogc:Or>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>aktif</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>active</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>pipe_type</ogc:PropertyName><ogc:Literal>main_line</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:And></ogc:Filter>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#16a34a</CssParameter><CssParameter name="stroke-width">5</CssParameter>
            <CssParameter name="stroke-linecap">round</CssParameter><CssParameter name="stroke-linejoin">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>
        <Rule>
          <Name>aktif_distribution</Name><Title>Aktif dağıtım hattı</Title>
          <ogc:Filter><ogc:And>
            <ogc:Or>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>aktif</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>active</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>pipe_type</ogc:PropertyName><ogc:Literal>distribution</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:And></ogc:Filter>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#16a34a</CssParameter><CssParameter name="stroke-width">3.5</CssParameter>
            <CssParameter name="stroke-linecap">round</CssParameter><CssParameter name="stroke-linejoin">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>
        <Rule>
          <Name>aktif_service_line</Name><Title>Aktif servis hattı</Title>
          <ogc:Filter><ogc:And>
            <ogc:Or>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>aktif</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>active</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>pipe_type</ogc:PropertyName><ogc:Literal>service_line</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:And></ogc:Filter>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#16a34a</CssParameter><CssParameter name="stroke-width">2.5</CssParameter>
            <CssParameter name="stroke-linecap">round</CssParameter><CssParameter name="stroke-linejoin">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>

        <Rule>
          <Name>pasif_main_line</Name><Title>Pasif ana hat</Title>
          <ogc:Filter><ogc:And>
            <ogc:Or>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>pasif</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>inactive</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>pipe_type</ogc:PropertyName><ogc:Literal>main_line</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:And></ogc:Filter>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#dc2626</CssParameter><CssParameter name="stroke-width">5</CssParameter>
            <CssParameter name="stroke-dasharray">9 5</CssParameter><CssParameter name="stroke-linecap">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>
        <Rule>
          <Name>pasif_distribution</Name><Title>Pasif dağıtım hattı</Title>
          <ogc:Filter><ogc:And>
            <ogc:Or>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>pasif</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>inactive</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>pipe_type</ogc:PropertyName><ogc:Literal>distribution</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:And></ogc:Filter>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#dc2626</CssParameter><CssParameter name="stroke-width">3.5</CssParameter>
            <CssParameter name="stroke-dasharray">9 5</CssParameter><CssParameter name="stroke-linecap">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>
        <Rule>
          <Name>pasif_service_line</Name><Title>Pasif servis hattı</Title>
          <ogc:Filter><ogc:And>
            <ogc:Or>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>pasif</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>inactive</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>pipe_type</ogc:PropertyName><ogc:Literal>service_line</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:And></ogc:Filter>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#dc2626</CssParameter><CssParameter name="stroke-width">2.5</CssParameter>
            <CssParameter name="stroke-dasharray">9 5</CssParameter><CssParameter name="stroke-linecap">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>

        <Rule>
          <Name>bakimda_main_line</Name><Title>Bakımda ana hat</Title>
          <ogc:Filter><ogc:And>
            <ogc:Or>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>bakımda</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>bakimda</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>maintenance</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>tamirde</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>pipe_type</ogc:PropertyName><ogc:Literal>main_line</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:And></ogc:Filter>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#f97316</CssParameter><CssParameter name="stroke-width">5</CssParameter>
            <CssParameter name="stroke-dasharray">5 4</CssParameter><CssParameter name="stroke-linecap">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>
        <Rule>
          <Name>bakimda_distribution</Name><Title>Bakımda dağıtım hattı</Title>
          <ogc:Filter><ogc:And>
            <ogc:Or>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>bakımda</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>bakimda</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>maintenance</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>tamirde</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>pipe_type</ogc:PropertyName><ogc:Literal>distribution</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:And></ogc:Filter>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#f97316</CssParameter><CssParameter name="stroke-width">3.5</CssParameter>
            <CssParameter name="stroke-dasharray">5 4</CssParameter><CssParameter name="stroke-linecap">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>
        <Rule>
          <Name>bakimda_service_line</Name><Title>Bakımda servis hattı</Title>
          <ogc:Filter><ogc:And>
            <ogc:Or>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>bakımda</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>bakimda</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>maintenance</ogc:Literal></ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo matchCase="false"><ogc:PropertyName>status</ogc:PropertyName><ogc:Literal>tamirde</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:Or>
            <ogc:PropertyIsEqualTo><ogc:PropertyName>pipe_type</ogc:PropertyName><ogc:Literal>service_line</ogc:Literal></ogc:PropertyIsEqualTo>
          </ogc:And></ogc:Filter>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#f97316</CssParameter><CssParameter name="stroke-width">2.5</CssParameter>
            <CssParameter name="stroke-dasharray">5 4</CssParameter><CssParameter name="stroke-linecap">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>

        <Rule>
          <Name>bilinmeyen</Name><Title>Bilinmeyen durum</Title><ElseFilter/>
          <LineSymbolizer><Stroke>
            <CssParameter name="stroke">#6b7280</CssParameter><CssParameter name="stroke-width">2.5</CssParameter>
            <CssParameter name="stroke-dasharray">2 4</CssParameter><CssParameter name="stroke-linecap">round</CssParameter>
          </Stroke></LineSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
