/* OpenLayers geometrisini backend'in beklediği WKT metnine dönüştürür.
 * POINT ve LINESTRING türlerini kontrol ederek işler. */
import LineString from "ol/geom/LineString";
import Point from "ol/geom/Point";
import type Geometry from "ol/geom/Geometry";

function coordinateText(coordinate: number[]): string {
  if (coordinate.length < 2 || !Number.isFinite(coordinate[0]) || !Number.isFinite(coordinate[1])) {
    throw new Error("Geometri sonlu EPSG:3857 koordinatları içermelidir.");
  }
  return `${coordinate[0]} ${coordinate[1]}`;
}

export function geometryToWkt(geometry: Geometry): string {
  // POINT tek koordinat, LINESTRING sıralı koordinatlar olarak yazılır.
  if (geometry instanceof Point) {
    return `POINT (${coordinateText(geometry.getCoordinates())})`;
  }
  if (geometry instanceof LineString) {
    const coordinates = geometry.getCoordinates();
    const distinct = new Set(coordinates.map((coordinate) => coordinateText(coordinate)));
    if (coordinates.length < 2 || distinct.size < 2 || geometry.getLength() <= 0) {
      throw new Error("Boru çizimi en az iki farklı koordinat içermelidir.");
    }
    // Backend LineString'i tablo sözleşmesindeki MultiLineString'e güvenli biçimde dönüştürür.
    return `LINESTRING (${coordinates.map((coordinate) => coordinateText(coordinate)).join(", ")})`;
  }
  throw new Error("Desteklenmeyen çizim geometrisi.");
}
