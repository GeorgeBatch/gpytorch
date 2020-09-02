#!/usr/bin/env python3

import warnings

import torch

from ..constraints import Positive
from ..lazy import NonLazyTensor, MatmulLazyTensor, ConstantMulLazyTensor, RootLazyTensor
from .kernel import Kernel


class JaccardKernel(Kernel):
    r"""
    Computes a covariance matrix based on the Jaccard kernel
    between binary inputs :math:`\mathbf{x_1}` and :math:`\mathbf{x_2}`:

    .. math::
        \begin{equation*}
            k_\text{Jaccard}(\mathbf{x_1}, \mathbf{x_2}) = v\mathbf{x_1}^\top
            \mathbf{x_2}.
        \end{equation*}

    where

    * :math:`v` is a :attr:`variance` parameter.


    .. note::

        To implement this efficiently, we use a :obj:`gpytorch.lazy.RootLazyTensor` during training and a
        :class:`gpytorch.lazy.MatmulLazyTensor` during test. These lazy tensors represent matrices of the form
        :math:`K = XX^{\top}` and :math:`K = XZ^{\top}`. This makes inference
        efficient because a matrix-vector product :math:`Kv` can be computed as
        :math:`Kv=X(X^{\top}v)`, where the base multiply :math:`Xv` takes only
        :math:`O(nd)` time and space.

    Args:
        :attr:`variance_prior` (:class:`gpytorch.priors.Prior`):
            Prior over the variance parameter (default `None`).
        :attr:`variance_constraint` (Constraint, optional):
            Constraint to place on variance parameter. Default: `Positive`.
        :attr:`active_dims` (list):
            List of data dimensions to operate on.
            `len(active_dims)` should equal `num_dimensions`.
    """

    def __init__(self, num_dimensions=None, offset_prior=None, variance_prior=None, variance_constraint=None, **kwargs):
        super(JaccardKernel, self).__init__(**kwargs)
        if variance_constraint is None:
            variance_constraint = Positive()

        if num_dimensions is not None:
            # Remove after 1.0
            warnings.warn("The `num_dimensions` argument is deprecated and no longer used.", DeprecationWarning)
            self.register_parameter(name="offset", parameter=torch.nn.Parameter(torch.zeros(1, 1, num_dimensions)))
        if offset_prior is not None:
            # Remove after 1.0
            warnings.warn("The `offset_prior` argument is deprecated and no longer used.", DeprecationWarning)
        self.register_parameter(name="raw_variance", parameter=torch.nn.Parameter(torch.zeros(*self.batch_shape, 1, 1)))
        if variance_prior is not None:
            self.register_prior(
                "variance_prior", variance_prior, lambda: self.variance, lambda v: self._set_variance(v)
            )

        self.register_constraint("raw_variance", variance_constraint)

    @property
    def variance(self):
        return self.raw_variance_constraint.transform(self.raw_variance)

    @variance.setter
    def variance(self, value):
        self._set_variance(value)

    def _set_variance(self, value):
        if not torch.is_tensor(value):
            value = torch.as_tensor(value).to(self.raw_variance)
        self.initialize(raw_variance=self.raw_variance_constraint.inverse_transform(value))

    def forward(self, x1, x2, diag=False, last_dim_is_batch=False, **params):
        x1_ = x1 * self.variance.sqrt()
        if last_dim_is_batch:
            x1_ = x1_.transpose(-1, -2).unsqueeze(-1)

        if x1.size() == x2.size() and torch.equal(x1, x2):
            # Use RootLazyTensor when x1 == x2 for efficiency when composing
            # with other kernels
            return ConstantMulLazyTensor(NonLazyTensor(torch.ones(x1_.size()[0], x1.size()[0])), 3)

        else:
            x2_ = x2 * self.variance.sqrt()
            if last_dim_is_batch:
                x2_ = x2_.transpose(-1, -2).unsqueeze(-1)

            numerator = MatmulLazyTensor(x1_, x2_.transpose(-2, -1))

        if diag:
            return prod.diag()
        else:
            return prod
