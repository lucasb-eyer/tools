import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl


class Confusion(object):
    '''Confusion matrix class including incremental confusion computation.

    Instances of this class can be used to compute the confusion matrix
    and other typical scores for semantic segmentation problems. Either
    incrementally or in one call. All labels should be positive integers.
    With the exception of a negative void label. Methods for plotting and
    printing are included.
    '''

    def __init__(self, label_names, void_label=-1, label_count=None):
        '''Inits a Confusion matrix with label names and the void label.
        Parameters
        ----------
        label_names : list of strings or None
            A list of all label names. The void label name should not be
            included

        void_label : int (default: -1)
            This label will be ignored. It has to be negative.

        label_count : int or None (default: None)
            If label_names is None, this will be used to define the shape of
            the confusion matrix.

        Raises
        ------
        ValueError
            When both `label_names` and `label_count` is ``None``, or if
            `void_label` is positive, a `ValueError` is raised.
        '''
        if label_names is not None:
            self.label_names = (np.array(label_names).copy()).tolist()
        else:
            if label_count is None:
                raise ValueError('Either label_names or label_count has to be '
                                 'specified.')
            else:
                self.label_names = [str(i) for i in range(label_count)]

        if void_label >= 0:
            raise ValueError('The void label needs to be a negative number.')
        else:
            self.void_label = void_label

        self.class_count= len(self.label_names)
        self.reset()

    def reset(self):
        '''Reset all values to allow for a fresh computation.
        '''
        self.confusion = np.zeros((self.class_count,self.class_count), np.int64)
        self.confusion_normalized_row = None
        self.confusion_normalized_col = None
        self.global_score  = 0
        self.avg_score     = 0
        self.avg_iou_score = 0
        self.finished_computation = False

    def finish(self):
        '''Computes all scores given the accumulated data.
        '''
        total = np.sum(self.confusion)
        self.gt_sum_per_class = np.sum(self.confusion, 1)
        self.sum_per_class = np.sum(self.confusion, 0)
        self.global_score = np.sum(np.diag(self.confusion))/total
        diag = np.diag(self.confusion)
        union = self.gt_sum_per_class + self.sum_per_class - diag
        self.avg_score = np.nanmean(diag/self.gt_sum_per_class)
        self.avg_iou_score = np.nanmean(diag/union)
        self.confusion_normalized_row = (
            self.confusion.copy().T/self.gt_sum_per_class.astype(np.float32)).T
        self.confusion_normalized_col = (
            self.confusion.copy()/self.sum_per_class.astype(np.float32))

        self.finished_computation = True

    def incremental_update(self, gt, pred, allow_void_prediction=False,
                           update_finished=True):
        '''Update the confusion matrix with the provided data.

        Given the ground truth and predictions the stored confusion matrix is
        updated. If all scores have been computed before they become invalid
        after this operation and need to be recomputed. Updates can be done
        with a single image, a batch, or the complete dataset at once.

        gt : np.ndarray
            The ground truth image(s). Either a single image (WxH) or a tensor
            of several images (BxWxH).

        pred : np.ndarray
            The prediction image(s). Either a single image (WxH) or a tensor
            of several images (BxWxH). Needs the same shape as gt.

        allow_void_prediction : bool (default: False)
            Specifies if void predictions are allowed or not. Typically this is
            not desired and an exception is raised when predictions have void
            labels. When set to True, these labels are ignored during the
            computation.

        update_finished : bool (default: True)
            When set to False this method raise an exception if scores have
            been computed before. If left at True, nothing happens.

        Raises
        ------
        ValueError
            When `gt` and `pred` don't have matching shapes, when the labels
            are too large, or when `pred` contains void labels and
            `allow_void_prediction` is set to False a `ValueError` is raised.

        Exception
            When `update_finished` is set to false and this method is called
            after the the scores have been computed an `Exception` is raised.
        '''

        if gt.shape != pred.shape:
            raise ValueError('Groundtruth and prediction shape missmatch')

        if not allow_void_prediction and self.void_label in pred:
            raise ValueError('Void labels found in the predictions. Fix the '
                             'predictions, or set `allow_void_prediction` to '
                             'True.')

        if np.max(gt) >= self.class_count:
            raise ValueError('Labels in the groundturh exceed the class count.')

        if np.max(pred) >= self.class_count:
            raise ValueError('Labels in the prediction exceed the class count.')

        if self.finished_computation and not update_finished:
            raise Exception('You specified not to allow updates after computing'
                            ' scores.')

        gt_flat = gt.flatten().astype(np.int32)
        pred_flat = pred.flatten().astype(np.int32)
        non_void = gt_flat != self.void_label
        if allow_void_prediction:
            non_void *= pred_flat != self.void_label
        gt_flat = gt_flat[non_void]
        pred_flat = pred_flat[non_void]
        pairs = gt_flat*self.class_count + pred_flat
        pairs, pair_counts = np.unique(pairs, return_counts=True)
        self.confusion.flat[pairs] += pair_counts

        self.finished_computation = False

    def plot(self, colormap=None, number_format=None, only_return_fig=False):
        '''Create and plot a figure summarizing all information.

        colormap : mpl.cm (default: None)
            The colormap used to colorize the matrices. None results in mpl
            default to be used.

        number_format : string or None (default: None)
            The format used to print percentages into the confusion matrix. When
            not provided the numbers are not printed.

        only_return_fig : bool (default: False)
            When set to true the figure is only returned. For example for saving
            the figure or when using this outside of jupyter notebooks.
        '''

        #Compute the values in case this has not been done yet.
        if not self.finished_computation:
            self.finish()

        #Setup the plots
        fig, ax = plt.subplots(1,2, figsize=(15,5.5), sharey=True, sharex=True)

        #Show the confusion matrices
        ax[0].imshow(self.confusion_normalized_row*100, interpolation='nearest',
                     cmap=colormap, vmin=0, vmax=100, aspect='auto')
        im = ax[1].imshow(
            self.confusion_normalized_col*100, interpolation='nearest',
            cmap=colormap, vmin=0, vmax=100, aspect='auto')

        #Make a colorbar
        cax,kw = mpl.colorbar.make_axes([a for a in ax.flat])
        plt.colorbar(im, cax=cax, **kw)
        ax[0].set_yticks(range(self.class_count))
        ax[0].set_xticks(range(self.class_count))

        #Possibly add the numbers
        if number_format is not None:
            for r in range(0,self.class_count):
                for c in range(0,self.class_count):
                    ax[0].text(c, r, '{0:>7.2%}'.format(
                        self.confusion_normalized_row[r,c]),
                        horizontalalignment='center',
                        verticalalignment='center', fontsize=10)
                    ax[1].text(c, r, '{0:>7.2%}'.format(
                        self.confusion_normalized_col[r,c]),
                        horizontalalignment='center',
                        verticalalignment='center', fontsize=10)

        # Add the names
        ax[0].set_yticklabels(self.label_names)
        ax[0].xaxis.tick_top()
        ax[0].set_xticklabels(self.label_names, rotation='vertical')
        ax[1].xaxis.tick_top()
        ax[1].set_xticklabels(self.label_names, rotation='vertical')

        # Labels for Row vs Column normalized
        ax[0].set_title('Row normalized', horizontalalignment='center', y=-0.1)
        ax[1].set_title(
            'Column normalized', horizontalalignment='center', y=-0.1)

        # A final line showing our three favorite scores.
        fig.suptitle('Global:{0:.2%}, Average:{1:.2%}, IoU:{2:.2%}'.format(
            self.global_score, self.avg_score, self.avg_iou_score), fontsize=14,
            fontweight='bold', x = 0.4, y = 0.03)

        if only_return_fig:
            plt.close()
            return fig

    def print_confusion_matrix(self, max_name_length=None):
        '''Print the row normalized confusion matrix in a human readable form.

        Parameters
        ----------
        max_name_length : int or None (default:None)
            The maximum number of characters printed for the class names.
            If left as None the longest class name defines this value.
        '''
        if max_name_length is None:
            max_name_length = np.max([len(n) for n in self.label_names])

        label_names_cropped = [n[:max_name_length] for n in self.label_names]

        #Compute the values in case this has not been done yet.
        if not self.finished_computation:
            self.finish()

        line = ('{:>' + str(max_name_length) + 's}, ' +
            ', '.join(['{:>7.2%}'] * self.class_count))
        for l, conf in zip(label_names_cropped, self.confusion_normalized_row):
            print(line.format(l, *(conf.tolist())))

        print('Global:  {:>7.2%}'.format(self.global_score))
        print('Average: {:>7.2%}'.format(self.avg_score))
        print('IoU:     {:>7.2%}'.format(self.avg_iou_score))