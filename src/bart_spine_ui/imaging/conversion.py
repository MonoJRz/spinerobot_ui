import numpy as np
import SimpleITK as sitk
import vtk
from vtk.util import numpy_support


def sitk_to_vtk(image: sitk.Image) -> vtk.vtkImageData:
    """
    Convert a scalar SimpleITK image into vtkImageData.

    The current viewer canonicalizes images to LPS before conversion. The VTK image therefore
    uses an axis-aligned patient-space representation suitable for the current orthogonal MPR
    implementation.
    """
    if image.GetNumberOfComponentsPerPixel() != 1:
        image = sitk.VectorIndexSelectionCast(image, 0)

    array_zyx = np.ascontiguousarray(sitk.GetArrayFromImage(image))

    size = image.GetSize()
    spacing = image.GetSpacing()
    origin = image.GetOrigin()

    vtk_image = vtk.vtkImageData()
    vtk_image.SetDimensions(int(size[0]), int(size[1]), int(size[2]))
    vtk_image.SetSpacing(float(spacing[0]), float(spacing[1]), float(spacing[2]))
    vtk_image.SetOrigin(float(origin[0]), float(origin[1]), float(origin[2]))

    vtk_array = numpy_support.numpy_to_vtk(
        num_array=array_zyx.ravel(order="C"),
        deep=True,
        array_type=numpy_support.get_vtk_array_type(array_zyx.dtype),
    )
    vtk_array.SetName("Scalars")
    vtk_image.GetPointData().SetScalars(vtk_array)
    return vtk_image
