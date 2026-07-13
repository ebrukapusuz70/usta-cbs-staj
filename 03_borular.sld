<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
    <NamedLayer>
        <Name>borular</Name>
        <UserStyle>
            <Title>Borular Temel Stil</Title>
            <FeatureTypeStyle>
                <Rule>
                    <Name>borular_line</Name>
                    <Title>Boru Hatlari</Title>
                    <LineSymbolizer>
                        <Stroke>
                            <CssParameter name="stroke">#E31A1C</CssParameter>
                            <CssParameter name="stroke-width">2.5</CssParameter>
                            <CssParameter name="stroke-linecap">round</CssParameter>
                            <CssParameter name="stroke-linejoin">round</CssParameter>
                        </Stroke>
                    </LineSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
