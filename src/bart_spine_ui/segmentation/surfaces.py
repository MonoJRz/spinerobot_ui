"""Shared segmentation surface extraction for the viewer and CAD export."""

import math

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy

from .colors import VERTEBRA_LABEL_COUNT

SEGMENTATION_GAUSSIAN_SIGMA_VOXELS = 1.5
SEGMENTATION_GAUSSIAN_RADIUS_FACTOR = 2.0


def create_smoothed_segmentation_surface(label_image: vtk.vtkImageData) -> vtk.vtkPolyData:
    """Extract gently Gaussian-smoothed surfaces without mixing adjacent labels."""

    dimensions = label_image.GetDimensions()
    labels_zyx = vtk_to_numpy(label_image.GetPointData().GetScalars()).reshape(
        dimensions[2], dimensions[1], dimensions[0]
    )
    padding = math.ceil(SEGMENTATION_GAUSSIAN_SIGMA_VOXELS * SEGMENTATION_GAUSSIAN_RADIUS_FACTOR)

    surfaces = vtk.vtkAppendPolyData()
    for label in range(1, VERTEBRA_LABEL_COUNT + 1):
        locations = np.argwhere(labels_zyx == label)
        if locations.size == 0:
            continue
        z_min, y_min, x_min = locations.min(axis=0)
        z_max, y_max, x_max = locations.max(axis=0)

        extract = vtk.vtkExtractVOI()
        extract.SetInputData(label_image)
        extract.SetVOI(
            max(0, int(x_min) - padding),
            min(dimensions[0] - 1, int(x_max) + padding),
            max(0, int(y_min) - padding),
            min(dimensions[1] - 1, int(y_max) + padding),
            max(0, int(z_min) - padding),
            min(dimensions[2] - 1, int(z_max) + padding),
        )

        binary_mask = vtk.vtkImageThreshold()
        binary_mask.SetInputConnection(extract.GetOutputPort())
        binary_mask.ThresholdBetween(label, label)
        binary_mask.SetInValue(1)
        binary_mask.SetOutValue(0)
        binary_mask.SetOutputScalarTypeToUnsignedChar()

        float_mask = vtk.vtkImageCast()
        float_mask.SetInputConnection(binary_mask.GetOutputPort())
        float_mask.SetOutputScalarTypeToFloat()

        gaussian = vtk.vtkImageGaussianSmooth()
        gaussian.SetInputConnection(float_mask.GetOutputPort())
        gaussian.SetDimensionality(3)
        gaussian.SetStandardDeviations(
            SEGMENTATION_GAUSSIAN_SIGMA_VOXELS,
            SEGMENTATION_GAUSSIAN_SIGMA_VOXELS,
            SEGMENTATION_GAUSSIAN_SIGMA_VOXELS,
        )
        gaussian.SetRadiusFactors(
            SEGMENTATION_GAUSSIAN_RADIUS_FACTOR,
            SEGMENTATION_GAUSSIAN_RADIUS_FACTOR,
            SEGMENTATION_GAUSSIAN_RADIUS_FACTOR,
        )

        contour = vtk.vtkFlyingEdges3D()
        contour.SetInputConnection(gaussian.GetOutputPort())
        contour.SetValue(0, 0.5)
        contour.ComputeNormalsOn()
        contour.ComputeGradientsOff()
        contour.ComputeScalarsOff()
        contour.Update()

        surface = vtk.vtkPolyData()
        surface.ShallowCopy(contour.GetOutput())
        if surface.GetNumberOfPoints() == 0:
            continue

        labels = vtk.vtkUnsignedCharArray()
        labels.SetName("VertebraLabel")
        labels.SetNumberOfTuples(surface.GetNumberOfPoints())
        labels.Fill(label)
        surface.GetPointData().SetScalars(labels)
        surfaces.AddInputData(surface)

    surfaces.Update()
    output = vtk.vtkPolyData()
    output.ShallowCopy(surfaces.GetOutput())
    return output
